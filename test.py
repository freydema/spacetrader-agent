import os

from SpaceTraderClient import SpaceTraderClient
import dotenv
import logging


logging.basicConfig(
    level=logging.INFO,  # or INFO, WARNING, ERROR depending on verbosity
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

dotenv.load_dotenv()
account_token = os.getenv("ACCOUNT_TOKEN")
agent_token= os.getenv("AGENT_TOKEN")

client = SpaceTraderClient()
# client.register_agent(callsign="DUMMY", faction="COSMIC")
my_agent = client.get_my_agent()
headquarters = my_agent["data"]["headquarters"]
headquarters_info = client.get_waypoint_info(headquarters)
my_contracts = client.get_my_contracts()
my_ships = client.get_my_ships()
ship = my_ships["data"][0]["symbol"]

contract_id = my_contracts["data"][0]["id"]
client.accept_contract(contract_id)
# new_contract = client.negotiate_new_contract(ship)