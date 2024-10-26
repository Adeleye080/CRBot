from flask import (
    Flask, render_template, request,
    jsonify,
)
import requests

app = Flask(__name__)

# Function to fetch GitHub user details
def get_github_profile(username):
    user_url = f"https://api.github.com/users/{username}"
    repos_url = f"https://api.github.com/users/{username}/repos"
    
    user_response = requests.get(user_url)
    repos_response = requests.get(repos_url)

    if user_response.status_code == 200 and repos_response.status_code == 200:
        user_data = user_response.json()
        repos_data = repos_response.json()

        # Process the data you want to include
        user_info = {
            "username": user_data.get("login"),
            "name": user_data.get("name"),
            "bio": user_data.get("bio"),
            "avatar_url": user_data.get("avatar_url"),
            "company": user_data.get("company"),
            "location": user_data.get("location"),
            "blog": user_data.get("blog"),
            "public_repos": user_data.get("public_repos"),
            "followers": user_data.get("followers"),
            "following": user_data.get("following"),
            "created_at": user_data.get("created_at"),
            "repos": [
                {
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "language": repo.get("language"),
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "updated_at": repo.get("updated_at"),
                }
                for repo in repos_data
            ]
        }
        return user_info
    else:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/profile', methods=['GET'])
def profile():
    username = request.args.get('username')
    user_info = get_github_profile(username)
    if user_info:
        return render_template('profile.html', user=user_info)
    else:
        return render_template('profile.html', error="User not found")
    

@app.route('/suggestions', methods=['GET'])
def suggestions():
    query = request.args.get('query')
    if query:
        suggestion_url = f"https://api.github.com/search/users?q={query}+in:login&type=Users"
        response = requests.get(suggestion_url)
        
        if response.status_code == 200:
            results = response.json().get('items', [])
            usernames = [user["login"] for user in results]
            return jsonify(usernames=usernames)
    return jsonify(usernames=[])


if __name__ == '__main__':
    app.run(debug=True)
