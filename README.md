# sems-digital-twin-map
An interactive map to visualize datasets from the [Urban Data Hub](https://api.hamburg.de/datasets/v1/).

![Screenshot of Map](/docs/img/screenshot_map.png)

## Setup
To quickly set up the project, follow these steps:
1. Clone the repository (`git clone https://github.com/semantic-systems/sems-digital-twin-map`)
2. Configure the `.env.example` file in the base directory and rename it to `.env`
3. Launch the project with `docker compose up -d --build`

This will launch a simple Dash Flask server accessible under [http://localhost:8050/](http://localhost:8050/). For more information on the setup, see [here](/docs/setup.md).