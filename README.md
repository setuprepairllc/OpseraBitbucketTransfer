# OpseraBitbucketTransfer
Transfers a list of bitbucket repositories from a file and imports them into github

How to use:
Create a file named repos.txt in the same directory as the script.
Add your Bitbucket repository URLs, one per line, for example:
Copy
https://bitbucket.org/your_workspace/repo1.git
https://bitbucket.org/your_workspace/repo2.git
Run the script.
This will read the URLs from the file and process each repository accordingly.

Authentication:
Create a .env file



Dependencies

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

![image](https://github.com/user-attachments/assets/5c96b520-8852-466a-ac45-de2fcd0d7cb1)
