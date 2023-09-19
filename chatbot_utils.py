import openai
import time
import requests
import re
import json
import logging

# Set up your API keys here or load them from environment variables

# Define a class for managing the dialog context
class DialogContext:
    def __init__(self, maxlen=5):
        self.maxlen = maxlen
        self.history = []

    def add_message(self, role, content):
        if len(self.history) >= self.maxlen:
            self.history.pop(0)
        self.history.append({"role": role, "content": content})

    def get_messages(self):
        return self.history.copy()

# Function to get the current date and time
def get_current_datetime():
    return str(time.strftime("%Y-%m-%d, %H:%M:%S"))

# Function to make a call to OpenAI's GPT-3
def call_openai_gpt(messages, model="gpt-3.5-turbo", temperature=1.0):
    start_time = time.time()
    response = openai.ChatCompletion.create(
        model=model, messages=messages, temperature=temperature
    )
    elapsed_time = (time.time() - start_time) * 1000
    cost_factor = 0.04
    cost = cost_factor * (response.usage["total_tokens"] / 1000)
    message = response.choices[0].message.content.strip()
    return message, cost, elapsed_time

# Function to scrape a URL and return a job ID for async processing
def scrape_and_summarize_url(url, scraperapi_key):
    api_url = 'https://async.scraperapi.com/jobs'
    data = {
        "apiKey": scraperapi_key,
        "url": url,
        "render": "document.querySelector('body').innerHTML = document.querySelector('.main-content').innerHTML"
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(api_url, headers=headers, json=data)
    logging.info(f"ScraperAPI response: {response.text}")
    if response.status_code == 200:
        job = response.json()
        return job["id"]
    else:
        return None

# Function to check the completion status of a scraping job
def check_job_completion(job_id):
    while True:
        time.sleep(10)  # Check status every 10 seconds
        status_url = f"https://async.scraperapi.com/jobs/{job_id}"
        response = requests.get(status_url)
        logging.info(f"ScraperAPI response: {response.text}")
        if response.status_code == 200:
            job = response.json()
            if job["status"] == "finished":
                # Once the job is completed, retrieve the result
                result_url = f"https://async.scraperapi.com/jobs/{job_id}"
                result_response = requests.get(result_url)
                if result_response.text:
                    try:
                        result = result_response.json()
                        system_prompt = "Please provide a brief summary (under 4000 tokens): " + str(result)
                        summary, _, _ = call_openai_gpt([{"role": "system", "content": system_prompt}])
                        return summary
                    except json.JSONDecodeError:
                        logging.error("Failed to decode JSON from result response")
                        logging.error(f"Result response text: {result_response.text}")
                        return None
                else:
                    logging.error("Empty response received from result URL")
                    return None

    return None
