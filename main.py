import openai
import os
import time
import requests
import re
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set up API keys
openai.api_key = os.getenv("OPENAI")
scraperapi_key = os.getenv("SCRAPERAPI")
brave_search_api_key = os.getenv("BRAVESEARCH")

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

def get_current_datetime():
    return str(time.strftime("%Y-%m-%d, %H:%M:%S"))

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

def scrape_and_summarize_url(url):
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
                        print(summary)
                        break
                    except json.JSONDecodeError:
                        logging.error("Failed to decode JSON from result response")
                        logging.error(f"Result response text: {result_response.text}")
                        break
                else:
                    logging.error("Empty response received from result URL")
                    break

def main():
    print("Welcome to the Chatbot CLI!")
    dialog_context = DialogContext()

    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        # Give any name 
        system_prompt = f"Hello, I'm your virtual assistant Nebula. The current time is {get_current_datetime()}."

        dialog_context.add_message("system", system_prompt)

        # Parse temperature
        temp_match = re.search(r'::temperature=([0-9]*\.?[0-9]+)::', user_input)
        temperature = 1.0  # Default temperature
        if temp_match:
            temperature = float(temp_match.group(1))
            user_input = re.sub(r'::temperature=([0-9]*\.?[0-9]+)::', '', user_input)

        # Parse model
        model_match = re.search(r'::model=(\w+[-]*\w+\.?\w*)::', user_input)
        model = "gpt-3.5-turbo"  # Default model
        if model_match:
            model = model_match.group(1)
            user_input = re.sub(r'::model=(\w+[-]*\w+\.?\w*)::', '', user_input)

        # Parse URL for scraping
        url_match = re.search(r'\bhttps?://\S+\b', user_input)
        if url_match:
            url = url_match.group()
            logging.info(f"Detected URL: {url}")
            job_id = scrape_and_summarize_url(url)
            if job_id:
                print(f"Request to scrape {url} received. Job started with ID: {job_id}")
                check_job_completion(job_id)
            else:
                print("Sorry, there was an issue starting the scraping job. Please try again later.")
            continue

        dialog_context.add_message("user", user_input)

        ai_response, cost, elapsed_time = call_openai_gpt(dialog_context.get_messages(), model=model, temperature=temperature)
        logging.info(f"Generated AI response: {ai_response}")
        logging.info(f"AI response cost: {cost}, elapsed time: {elapsed_time}")
        dialog_context.add_message("assistant", ai_response)

        print("Chatbot:", ai_response)

if __name__ == "__main__":
    main()
