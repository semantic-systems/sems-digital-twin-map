FROM python:3.8-slim

# Set the working directory to /app
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /app
COPY . .

# Install the packages in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8050 available to the world outside this container
EXPOSE 8050

# Define environment variable, used for determining the host name of the database
ENV IN_DOCKER=true

# Start the app with python main.py
CMD python ./main.py