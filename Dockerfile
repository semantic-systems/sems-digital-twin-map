FROM python:3.8-slim

# Set the working directory to /app
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8050 available to the world outside this container
EXPOSE 8050

# Define environment variable
ENV NAME World

# Run main.py when the container launches
CMD ["python", "./main.py"]