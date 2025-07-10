#!/usr/bin/env python3

import pyfiglet; print(pyfiglet.figlet_format("OPSERA"))
print("Bitbucket to GitHub Repo Migration Tool\n")

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

BITBUCKET_USERNAME = os.getenv('BITBUCKET_USERNAME')
BITBUCKET_APP_PASSWORD = os.getenv('BITBUCKET_APP_PASSWORD')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_API_URL = 'https://api.github.com'

CLONE_DIR = 'temp_repos'
VERBOSE = True

def vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)

def create_github_repo(repo_name):
    url = f"{GITHUB_API_URL}/user/repos"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    base_name = repo_name
    suffix = 0
    while True:
        name_to_try = base_name if suffix == 0 else f"{base_name}-{suffix}"
        data = {'name': name_to_try, 'private': False}
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 201:
            logging.info(f"GitHub repo '{name_to_try}' created successfully.")
            vprint(f"[+] GitHub repo '{name_to_try}' created successfully.")
            return name_to_try
        elif response.status_code == 422:
            suffix += 1
            vprint(f"[!] GitHub repo '{name_to_try}' already exists. Trying a new name...")
            continue
        else:
            logging.error(f"Failed to create GitHub repo '{name_to_try}': {response.text}")
            vprint(f"[-] Failed to create GitHub repo '{name_to_try}': {response.text}")
            return None

def add_auth_to_url(repo_url, username, password):
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
    """Clone the Bitbucket repository locally with authentication, all branches and tags.
    After cloning, check out every remote branch and print the files in the working directory."""
    try:
        repo_path = os.path.join(CLONE_DIR, repo_name)
        if os.path.exists(repo_path):
            vprint(f"[i] Repository {repo_name} already cloned. Removing and recloning.")
            logging.info(f"Repository {repo_name} already cloned. Removing and recloning.")
            shutil.rmtree(repo_path)

        auth_repo_url = add_auth_to_url(repo_url, BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD)

        vprint(f"[i] Cloning Bitbucket repo {repo_url} with authentication (all branches and tags)...")
        logging.info(f"Cloning Bitbucket repo {repo_url} with authentication (all branches and tags)...")
        repo = Repo.clone_from(auth_repo_url, repo_path, multi_options=['--no-single-branch'])
        repo.git.fetch('--all', '--tags')

        # List all remote branches and check them out locally, printing files for each
        remote_refs = repo.git.branch('-r').split('\n')
        remote_heads = [r.strip() for r in remote_refs if '->' not in r and r.strip()]
        local_branches = []
        for remote_branch in remote_heads:
            if remote_branch.startswith('origin/'):
                branch_name = remote_branch.replace('origin/', '', 1)
                # Only create the branch if it doesn't already exist
                if branch_name not in repo.heads:
                    repo.git.checkout('-b', branch_name, remote_branch)
                else:
                    repo.git.checkout(branch_name)
                local_branches.append(branch_name)
                files = os.listdir(repo_path)
                vprint(f"[i] Files in {repo_name} on branch '{branch_name}': {files}")

        vprint(f"[+] Cloned {repo_name} successfully.")
        logging.info(f"Cloned {repo_name} successfully.")

        tags = [tag.name for tag in repo.tags]
        vprint(f"[i] Tags in cloned repo {repo_name}: {tags}")

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
    try:
        repo = Repo(repo_path)
        if 'github' in [remote.name for remote in repo.remotes]:
            repo.delete_remote('github')
        github_url = f'https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{repo_name}.git'
        repo.create_remote('github', github_url)
        vprint(f"[i] Pushing all branches to GitHub for {repo_name}...")
        logging.info(f"Pushing all branches to GitHub for {repo_name}...")
        repo.git.push('github', '--all')
        if repo.tags:
            vprint(f"[i] Pushing tags to GitHub for {repo_name}...")
            repo.git.push('github', '--tags')
        else:
            vprint(f"[i] No tags to push for {repo_name}.")
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

    repo_file = 'repos.txt'
    bitbucket_repos = read_repos_from_file(repo_file)

    vprint(f"[i] Starting migration of {len(bitbucket_repos)} repositories...")

    for repo_url in tqdm(bitbucket_repos, desc="Migrating repos", unit="repo"):
        try:
            repo_name = repo_url.rstrip('.git').split('/')[-1]
            logging.info(f"Starting migration for {repo_name}")
            vprint(f"\n[i] Starting migration for {repo_name}")

            created_repo_name = create_github_repo(repo_name)
            if not created_repo_name:
                logging.error(f"Skipping {repo_name} due to GitHub repo creation failure.")
                vprint(f"[-] Skipping {repo_name} due to GitHub repo creation failure.")
                continue

            repo_path = clone_bitbucket_repo(repo_url, created_repo_name)
            if not repo_path:
                logging.error(f"Skipping {created_repo_name} due to clone failure.")
                vprint(f"[-] Skipping {created_repo_name} due to clone failure.")
                continue

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
