"""
Flask API for the FinanceGuard Expense RAG Chatbot.

Usage:
    python app.py
    curl -X POST http://localhost:5001/chat -H "Content-Type: application/json" \
         -d '{"question": "What is the meal expense limit?"}'
"""
from flask import Flask, request, jsonify
from rag import query_rag

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    result = query_rag(data["question"])
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
