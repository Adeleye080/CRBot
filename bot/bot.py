import os
import json
import time
import subprocess
import tempfile
import shutil
import hashlib
import hmac
from flask import Flask, request, jsonify
import jwt
import requests
from utils import (
    generate_jwt, verify_webhook,
    get_installation_access_token
)

# Load environment variables
from dotenv import load_dotenv

load_dotenv()



PORT = os.getenv("PORT", 3000)

app = Flask(__name__)

# GitHub JWT for authentication


# Verify webhook signature

# Fetch installation access token


# Execute a command and return output
def exec_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.stderr:
        raise ValueError(result.stderr)
    return result.stdout

# Function to create a temporary directory
def create_temp_dir():
    temp_dir = os.path.join(tempfile.gettempdir(), f"github-code-checker-{int(time.time())}")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

# Function to download a file
def download_file(url, dest):
    response = requests.get(url, stream=True)
    with open(dest, "wb") as file:
        shutil.copyfileobj(response.raw, file)

# Download PR files to temporary directory
def download_pr_files(pull_request, token):
    temp_dir = create_temp_dir()  # Create temporary directory
    files = []
    url = f"{pull_request['_links']['self']['href']}/files"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    # Loop through each file and download it to the temporary directory
    for file in response.json():
        file_url = file["raw_url"]
        file_path = os.path.join(temp_dir, file["filename"])

        download_file(file_url, file_path)  # Download file to temp directory
        files.append({"filename": file["filename"], "path": file_path})

    print("Downloaded files:", files)
    return files

# Check Python files using flake8
def check_python_formatting(files):
    comments = []
    for file in files:
        try:
            lint_result = exec_command(f"flake8 {file['path']}")
        except ValueError as e:
            comments.append({
                "path": file["filename"],
                "message": "PEP8 issues detected",
                "issues": e.stdout.strip().split("\n")
            })
    return comments

# Check JavaScript files using eslint
def check_javascript_formatting(files):
    comments = []
    for file in files:
        try:
            lint_result = exec_command(f"eslint --config eslint.config.js {file['path']}")
            comments.append({
                "path": file["filename"],
                "message": "ESLint issues detected",
                "issues": lint_result.strip().split("\n")
            })
        except ValueError as e:
            print(f"eslint error for {file['filename']}:", e)
    return comments

# Post comments on PR
def post_pr_comments(pull_request, comments, token):
    url = f"https://api.github.com/repos/{pull_request['base']['repo']['full_name']}/issues/{pull_request['number']}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    for comment in comments:
        body = f"### 🚨Code formatting issues detected!🚨\n\nFile: `{comment['path']}`\n\n**{comment['message']}**\n\n" + "\n".join(comment['issues'])
        response = requests.post(url, json={"body": body}, headers=headers)
        response.raise_for_status()

# Delete temporary directory after processing
def delete_temp_dir(temp_dir):
    shutil.rmtree(temp_dir)
    print(f"Temporary directory {temp_dir} deleted")

# Handle webhook events
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        verify_webhook(request)
        action = request.json["action"]
        pull_request = request.json["pull_request"]
        installation = request.json["installation"]

        if action in ["opened", "synchronize"]:
            token = get_installation_access_token(installation["id"])
            pr_files = download_pr_files(pull_request, token)

            python_files = [file for file in pr_files if file["filename"].endswith(".py")]
            js_files = [file for file in pr_files if file["filename"].endswith(".js")]

            python_comments = check_python_formatting(python_files)
            js_comments = check_javascript_formatting(js_files)

            all_comments = python_comments + js_comments
            if all_comments:
                post_pr_comments(pull_request, all_comments, token)

            # Delete the temporary directory after processing
            delete_temp_dir(os.path.dirname(pr_files[0]["path"]))
        return jsonify({"message": "Webhook processed"}), 200
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({"error": str(e)}), 400

@app.route("/", methods=["GET"])
def home():
    return "<h2> You are welcome! </h2>"

if __name__ == "__main__":
    app.run(port=PORT)
