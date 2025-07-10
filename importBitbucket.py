import os
import shutil
import logging
import requests
from git import Repo, GitCommandError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    filename='repo_migration.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Read credentials from environment variables
BITBUCKET_USERNAME = os.getenv('BITBUCKET_USERNAME')
BITBUCKET_APP_PASSWORD = os.getenv('BITBUCKET_APP_PASSWORD')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
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
    """Clone the Bitbucket repository locally with authentication."""
    try:
        repo_path = os.path.join(CLONE_DIR, repo_name)
        if os.path.exists(repo_path):
            logging.info(f"Repository {repo_name} already cloned. Removing and recloning.")
            shutil.rmtree(repo_path)

        # Insert authentication into the repo URL
        if repo_url.startswith('https://'):
            auth_repo_url = repo_url.replace(
                'https://',
                f'https://{BITBUCKET_USERNAME}:{BITBUCKET_APP_PASSWORD}@'
            )
        else:
            logging.error(f"Unsupported repo URL format: {repo_url}")
            return None

        logging.info(f"Cloning Bitbucket repo {repo_url} with authentication...")
        Repo.clone_from(auth_repo_url, repo_path)
        logging.info(f"Cloned {repo_name} successfully.")
        return repo_path
    except GitCommandError as e:
        logging.error(f"Error cloning {repo_name}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error cloning {repo_name}: {e}")
        return None

def push_to_github(repo_path, repo_name):
    """Push the cloned repo to GitHub."""
    try:
        repo = Repo(repo_path)

        # Remove existing 'github' remote if exists
        if 'github' in [remote.name for remote in repo.remotes]:
            repo.delete_remote('github')

        github_url = f'https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{repo_name}.git'
        origin = repo.create_remote('github', github_url)

        # Push all branches
        for ref in repo.refs:
            if ref.name.startswith('refs/heads/'):
                branch = ref.name.replace('refs/heads/', '')
                logging.info(f"Pushing branch {branch} to GitHub...")
                origin.push(refspec=f'refs/heads/{branch}:refs/heads/{branch}')

        logging.info(f"Pushed {repo_name} to GitHub successfully.")
        return True
    except GitCommandError as e:
        logging.error(f"Error pushing {repo_name} to GitHub: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error pushing {repo_name} to GitHub: {e}")
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
    if not all([BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD, GITHUB_USERNAME, GITHUB_TOKEN]):
        logging.error("Missing one or more authentication environment variables. Please check your .env file.")
        return

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
