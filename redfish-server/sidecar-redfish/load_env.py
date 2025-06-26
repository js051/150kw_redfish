'''
Run:
    python app.py --env=dev
'''
from argparse import ArgumentParser
import sys, os
from dotenv import load_dotenv
import yaml

arg_parser = ArgumentParser()
arg_parser.add_argument("--env", help="prod|stage|dev", default="prod")
# args = arg_parser.parse_args()
args, unknown = arg_parser.parse_known_args()

proj_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(proj_root)

if os.getenv("IS_TESTING_MODE") == "True": # if in testsing mode
    args.env = "test"
 
if args.env == "prod":
    dotenv_path = os.path.join(proj_root, '.env')
else:
    dotenv_path = os.path.join(proj_root, f'.env-{args.env}')  
print(f"Load env file: {dotenv_path}")  
load_dotenv(dotenv_path=dotenv_path, verbose=True, override=True)
os.environ["env"] = args.env

PROJECT_NAME = os.getenv("PROJ_NAME")

hardware_info: dict = {}
with open(os.path.join(proj_root, "etc", "hardware", f"{PROJECT_NAME}", "hardware_info.yaml"), encoding="utf-8") as f:
    hardware_info = yaml.safe_load(f)
    print("## hardware_info:")
    print(hardware_info)

redfish_info: dict = {}
with open(os.path.join(proj_root, "etc", "software", f"{PROJECT_NAME}", "redfish_info.yaml"), encoding="utf-8") as f:
    redfish_info = yaml.safe_load(f)
    print("## redfish_info:")
    print(redfish_info)