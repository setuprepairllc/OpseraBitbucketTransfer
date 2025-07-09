import os
import subprocess
import logging
import requests
from git import Repo, GitCommandError

# Configure logging
logging.basicConfig(
    filename='repo_migration.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants - replace with your actual tokens and usernames
BITBUCKET_USERNAME = 'your_bitbucket_username'
BITBUCKET_APP_PASSWORD = 'your_bitbucket_app_password'  # or OAuth token
GITHUB_USERNAME = 'your_github_username'
GITHUB_TOKEN = 'your_github_token'
GITHUB_API_URL = 'https://api.github.com'

# Directory to clone repos temporarily
CLONE_DIR = 'temp_repos'

def create_github_repo(repo_name):
    """Create a new GitHub repository."""
    url = f"{GITHUB_API_URL}/user/repos"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    data = {
        'name': repo_name,
        'private': False  # Change to True if you want private repos
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        logging.info(f"GitHub repo '{repo_name}' created successfully.")
        return True
    elif response.status_code == 422:
        logging.warning(f"GitHub repo '{repo_name}' already exists.")
        return True
    else:
        logging.error(f"Failed to create GitHub repo '{repo_name}': {response.text}")
        return False

def clone_bitbucket_repo(repo_url, repo_name):
    """Clone the Bitbucket repository locally."""
    try:
        repo_path = os.path.join(CLONE_DIR, repo_name)
        if os.path.exists(repo_path):
            logging.info(f"Repository {repo_name} already cloned. Removing and recloning.")
            subprocess.run(['rm', '-rf', repo_path], check=True)
        logging.info(f"Cloning Bitbucket repo {repo_url}...")
        Repo.clone_from(repo_url, repo_path)
        logging.info(f"Cloned {repo_name} successfully.")
        return repo_path
    except GitCommandError as e:
        logging.error(f"Error cloning {repo_name}: {e}")
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Error removing existing repo directory {repo_name}: {e}")
        return None

def push_to_github(repo_path, repo_name):
    """Push the cloned repo to GitHub."""
    try:
        repo = Repo(repo_path)
        origin = repo.create_remote('github', f'https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{repo_name}.git')
        origin.push(refspec='refs/heads/master:refs/heads/master')
        logging.info(f"Pushed {repo_name} to GitHub successfully.")
        return True
    except GitCommandError as e:
        logging.error(f"Error pushing {repo_name} to GitHub: {e}")
        return False

def read_repos_from_file(file_path):
    """Read repository URLs from a file, one per line."""
    try:
        with open(file_path, 'r') as f:
            repos = [line.strip() for line in f if line.strip()]
        logging.info(f"Read {len(repos)} repositories from {file_path}")
        return repos
    except Exception as e:
        logging.error(f"Failed to read repository list from {file_path}: {e}")
        return []

def main():
    if not os.path.exists(CLONE_DIR):
        os.makedirs(CLONE_DIR)

    repo_file = 'repos.txt'  # File containing Bitbucket repo URLs
    bitbucket_repos = read_repos_from_file(repo_file)

    for repo_url in bitbucket_repos:
        try:
            repo_name = repo_url.rstrip('.git').split('/')[-1]
            logging.info(f"Starting migration for {repo_name}")

            # Create GitHub repo
            if not create_github_repo(repo_name):
                logging.error(f"Skipping {repo_name} due to GitHub repo creation failure.")
                continue

            # Clone Bitbucket repo
            repo_path = clone_bitbucket_repo(repo_url, repo_name)
            if not repo_path:
                logging.error(f"Skipping {repo_name} due to clone failure.")
                continue

            # Push to GitHub
            if not push_to_github(repo_path, repo_name):
                logging.error(f"Failed to push {repo_name} to GitHub.")
                continue

            logging.info(f"Migration completed for {repo_name}")

        except Exception as e:
            logging.error(f"Unexpected error with {repo_url}: {e}")

if __name__ == '__main__':
    main()
