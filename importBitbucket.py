#!/usr/bin/env python3

import os
import shutil
import logging
import requests
from git import Repo, GitCommandError
from dotenv import load_dotenv
from tqdm import tqdm
from urllib.parse import urlparse, urlunparse

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

# Verbose flag
VERBOSE = True

print(f"Loaded GitHub username: {GITHUB_USERNAME}")
print(f"Loaded GitHub token (first 4 chars): {GITHUB_TOKEN[:4]}{'*' * (len(GITHUB_TOKEN)-4)}")

def vprint(*args, **kwargs):
    """Print only if verbose is enabled."""
    if VERBOSE:
        print(*args, **kwargs)

def create_github_repo(repo_name):
    """Create a new GitHub repository, appending a number if the name exists."""
    url = f"{GITHUB_API_URL}/user/repos"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

    base_name = repo_name
    suffix = 0

    while True:
        name_to_try = base_name if suffix == 0 else f"{base_name}-{suffix}"
        data = {
            'name': name_to_try,
            'private': False  # Change to True if you want private repos
        }
        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 201:
            logging.info(f"GitHub repo '{name_to_try}' created successfully.")
            vprint(f"[+] GitHub repo '{name_to_try}' created successfully.")
            return name_to_try  # Return the actual repo name created

        elif response.status_code == 422:
            # Repo name already exists, try next suffix
            suffix += 1
            vprint(f"[!] GitHub repo '{name_to_try}' already exists. Trying a new name...")
            continue

        else:
            logging.error(f"Failed to create GitHub repo '{name_to_try}': {response.text}")
            vprint(f"[-] Failed to create GitHub repo '{name_to_try}': {response.text}")
            return None

def add_auth_to_url(repo_url, username, password):
    """Add authentication credentials to a repo URL, handling existing usernames."""
    parsed = urlparse(repo_url)
    netloc = parsed.hostname
    if parsed.port:
        netloc += f":{parsed.port}"
    auth_netloc = f"{username}:{password}@{netloc}"
    new_url = urlunparse((
        parsed.scheme,
        auth_netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))
    return new_url

def clone_bitbucket_repo(repo_url, repo_name):
    """Clone the Bitbucket repository locally with authentication."""
    try:
        repo_path = os.path.join(CLONE_DIR, repo_name)
        if os.path.exists(repo_path):
            vprint(f"[i] Repository {repo_name} already cloned. Removing and recloning.")
            logging.info(f"Repository {repo_name} already cloned. Removing and recloning.")
            shutil.rmtree(repo_path)

        auth_repo_url = add_auth_to_url(repo_url, BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD)

        vprint(f"[i] Cloning Bitbucket repo {repo_url} with authentication...")
        logging.info(f"Cloning Bitbucket repo {repo_url} with authentication...")
        Repo.clone_from(auth_repo_url, repo_path)
        vprint(f"[+] Cloned {repo_name} successfully.")
        logging.info(f"Cloned {repo_name} successfully.")
        return repo_path
    except GitCommandError as e:
        logging.error(f"Error cloning {repo_name}: {e}")
        vprint(f"[-] Error cloning {repo_name}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error cloning {repo_name}: {e}")
        vprint(f"[-] Unexpected error cloning {repo_name}: {e}")
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
                vprint(f"[i] Pushing branch {branch} to GitHub...")
                logging.info(f"Pushing branch {branch} to GitHub...")
                origin.push(refspec=f'refs/heads/{branch}:refs/heads/{branch}')

        vprint(f"[+] Pushed {repo_name} to GitHub successfully.")
        logging.info(f"Pushed {repo_name} to GitHub successfully.")
        return True
    except GitCommandError as e:
        logging.error(f"Error pushing {repo_name} to GitHub: {e}")
        vprint(f"[-] Error pushing {repo_name} to GitHub: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error pushing {repo_name} to GitHub: {e}")
        vprint(f"[-] Unexpected error pushing {repo_name} to GitHub: {e}")
        return False

def read_repos_from_file(file_path):
    """Read repository URLs from a file, one per line."""
    try:
        with open(file_path, 'r') as f:
            repos = [line.strip() for line in f if line.strip()]
        logging.info(f"Read {len(repos)} repositories from {file_path}")
        vprint(f"[i] Read {len(repos)} repositories from {file_path}")
        return repos
    except Exception as e:
        logging.error(f"Failed to read repository list from {file_path}: {e}")
        vprint(f"[-] Failed to read repository list from {file_path}: {e}")
        return []

def main():
    if not all([BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD, GITHUB_USERNAME, GITHUB_TOKEN]):
        logging.error("Missing one or more authentication environment variables. Please check your .env file.")
        vprint("[-] Missing one or more authentication environment variables. Please check your .env file.")
        return

    if not os.path.exists(CLONE_DIR):
        os.makedirs(CLONE_DIR)

    repo_file = 'repos.txt'  # File containing Bitbucket repo URLs
    bitbucket_repos = read_repos_from_file(repo_file)

    vprint(f"[i] Starting migration of {len(bitbucket_repos)} repositories...")

    for repo_url in tqdm(bitbucket_repos, desc="Migrating repos", unit="repo"):
        try:
            repo_name = repo_url.rstrip('.git').split('/')[-1]
            logging.info(f"Starting migration for {repo_name}")
            vprint(f"\n[i] Starting migration for {repo_name}")

            # Create GitHub repo (with suffix if needed)
            created_repo_name = create_github_repo(repo_name)
            if not created_repo_name:
                logging.error(f"Skipping {repo_name} due to GitHub repo creation failure.")
                vprint(f"[-] Skipping {repo_name} due to GitHub repo creation failure.")
                continue

            # Clone Bitbucket repo
            repo_path = clone_bitbucket_repo(repo_url, created_repo_name)
            if not repo_path:
                logging.error(f"Skipping {created_repo_name} due to clone failure.")
                vprint(f"[-] Skipping {created_repo_name} due to clone failure.")
                continue

            # Push to GitHub
            if not push_to_github(repo_path, created_repo_name):
                logging.error(f"Failed to push {created_repo_name} to GitHub.")
                vprint(f"[-] Failed to push {created_repo_name} to GitHub.")
                continue

            logging.info(f"Migration completed for {created_repo_name}")
            vprint(f"[+] Migration completed for {created_repo_name}")

        except Exception as e:
            logging.error(f"Unexpected error with {repo_url}: {e}")
            vprint(f"[-] Unexpected error with {repo_url}: {e}")

if __name__ == '__main__':
    main()
