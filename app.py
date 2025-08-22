from flask import Flask, render_template, request, jsonify
import google.cloud.dialogflow as dialogflow
import boto3
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import uuid

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Dialogflow setup
PROJECT_ID = os.getenv("DIALOGFLOW_PROJECT_ID", "rational-poet-439409-v3")
try:
    session_client = dialogflow.SessionsClient()
    logging.info("Dialogflow client initialized successfully")
except Exception as e:
    logging.error(f"Failed to initialize Dialogflow client: {e}")
    raise

# AWS DynamoDB setup
try:
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv("AWS_REGION", "eu-north-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )
    table = dynamodb.Table("Conversations")
    logging.info("DynamoDB client initialized successfully")
except Exception as e:
    logging.error(f"Failed to initialize DynamoDB client: {e}")
    raise

# Save conversation to DynamoDB
def save_conversation(user_message, bot_response):
    try:
        table.put_item(
            Item={
                "id": str(uuid.uuid4()),
                "user_message": user_message,
                "bot_response": bot_response,
                "timestamp": datetime.now().isoformat()
            }
        )
        logging.info("Conversation saved to DynamoDB")
    except Exception as e:
        logging.error(f"Error saving to DynamoDB: {e}")

# Get analytics (total queries)
def get_stats():
    try:
        response = table.scan(Select='COUNT')
        return {"total_queries": response.get("Count", 0)}
    except Exception as e:
        logging.error(f"Error fetching stats: {e}")
        return {"total_queries": 0}

@app.route('/')
def index():
    logging.debug("Serving / route")
    try:
        return render_template('index.html')
    except Exception as e:
        logging.error(f"Error rendering index.html: {e}")
        return jsonify({"error": "Template not found"}), 404

@app.route('/chat', methods=['POST'])
def chat():
    logging.debug(f"Received /chat POST request: {request.json}")
    try:
        if not request.is_json:
            logging.warning("Invalid JSON in /chat request")
            return jsonify({"response": "Invalid request format"}), 400
        user_message = request.json.get('message')
        if not user_message:
            logging.warning("No message provided in /chat request")
            return jsonify({"response": "Please provide a message"}), 400
        session_id = request.json.get('session_id', str(uuid.uuid4()))
        session = session_client.session_path(PROJECT_ID, session_id)
        text_input = dialogflow.TextInput(text=user_message, language_code="en")
        query_input = dialogflow.QueryInput(text=text_input)
        response = session_client.detect_intent(session=session, query_input=query_input)
        bot_response = response.query_result.fulfillment_text or "Sorry, I didn't understand."
        save_conversation(user_message, bot_response)
        logging.info(f"User: {user_message}, Bot: {bot_response}")
        return jsonify({"response": bot_response, "session_id": session_id})
    except Exception as e:
        logging.error(f"Error in /chat route: {e}")
        return jsonify({"response": "Sorry, something went wrong."}), 500

@app.route('/stats', methods=['GET'])
def stats():
    logging.debug("Received /stats GET request")
    try:
        return jsonify(get_stats())
    except Exception as e:
        logging.error(f"Error in /stats route: {e}")
        return jsonify({"total_queries": 0}), 500

@app.errorhandler(404)
def page_not_found(e):
    logging.error(f"404 error: {request.url}")
    return jsonify({"error": "Page not found. Check the URL and try again."}), 404

if __name__ == '__main__':
    logging.info("Starting Flask server on http://localhost:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')