# Setup

## Setting up this project

First, add your credentials to the `.env.example` file in the base directory and rename it to `.env`.

If you want to use the reports server (see `python-server-reports` in [servers.md](/docs/servers.md)), you first need to install and configure the [sems-social-media-retriever](https://github.com/semantic-systems/sems-social-media-retriever) project. For more information, see the section *Configuring the Social Media Retriever*.

Then, run `docker compose up -d --build` in the project directory.

This will launch a simple dash Flask server accessible under [http://127.0.0.1:8050/](http://127.0.0.1:8050/)

## Configuration
All data is requested from [https://api.hamburg.de/datasets/v1/](https://api.hamburg.de/datasets/v1/). You can configure which API endpoints are used in `api_config.json`. For more information, see [datasources.md](/docs/datasources.md).

## Configuring the Social Media Retriever
To use the reports server and request social media data, you need to set up the [sems-social-media-retriever](https://github.com/semantic-systems/sems-social-media-retriever):

1. Clone the repository (`git clone https://github.com/semantic-systems/sems-social-media-retriever`)
2. In the social media retriever, add your credentials to `keys.env.example` and rename it to `keys.env`
3. Build the image of the social media retriever with the name `sems-social-media-requester` (`docker build -t sems-social-media-requester .`)