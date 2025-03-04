# Warm Transfer: Transfer support calls from one agent to another using Twilio, Elevenlabs Agent

## Local development

1. Clone this repository and `cd` into it.

   ```bash
   git clone --branch fastapi https://github.com/chai-dev682/warm-transfer-flask.git
   cd warm-transfer-flask
   ```

2. Create and activate a new python3 virtual environment.

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the requirements.

   ```bash
   pip install -r requirements.txt
   ```

4. Copy the sample configuration file and edit it to match your configuration.

   ```bash
   cp .env.example .env
   ```

   Twilio API credentials can be found [here](https://www.twilio.com/console) 
   and find you can create a REST API Key [here](https://www.twilio.com/console/project/api-keys).
   If using the twilio CLI you can run:
   
5. Expose your application to the wider internet using ngrok.

   To actually forward incoming calls, your development server will need to be publicly accessible.
   [We recommend using ngrok to solve this problem](https://www.twilio.com/blog/2015/09/6-awesome-reasons-to-use-ngrok-when-testing-webhooks.html).


   ```bash
   ngrok http 5000
   ```

   Once you have started ngrok, the public accessible URL will look like this:
   
   ```
   https://<your-ngrok-id>.ngrok.io/
   ```

6. Start the development server.

   ```bash
   python manage.py
   ```

7. Configure Twilio to call your webhooks.

   You will also need to configure Twilio to call your application when calls are received on your `TWILIO_NUMBER`. The voice URL should look something like this:
   
   ```
   http://<your-ngrok-id>.ngrok.io/conference/connect/client
   ```

That's it!

P.S. You need to change medical_service_number in [twilio.py](./app/routers/twilio.py), which is number where call is transferred.