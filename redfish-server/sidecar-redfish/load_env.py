'''
Run:
    python app.py --env=dev
'''
from argparse import ArgumentParser
import sys, os, platform
from dotenv import load_dotenv
import yaml

class AppPathInitializer:
    def __init__(self, params={}):
        self.platform = platform.system()
        

    def initialize(self):
        db_root = os.getenv("PROJ_SQLITE_ROOT", "")
        db_filename_suffix = "-test" if os.getenv("env") == "test" else ""
        db_filename = f"mydb{db_filename_suffix}.sqlite"
        db_filepath = os.path.join(db_root, db_filename)

        if self.platform in ['Linux', 'Darwin']:
            # Maybe it's better to move to installation process.
            if db_root != "" and not os.path.exists(db_root):
                print(f"Create folder: {db_root}")
                os.makedirs(db_root)

        elif self.platform == 'Windows':
            db_filepath = db_filename
        
        return {
            "db_filename": db_filename,
            "db_filepath": db_filepath
        }
        


arg_parser = ArgumentParser()
arg_parser.add_argument("--env-file", help=".env file path", default="") # For testing
arg_parser.add_argument("--env", help="prod|stage|dev", default="") # For running app
# args = arg_parser.parse_args()
args, unknown = arg_parser.parse_known_args()

proj_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(proj_root)

if os.getenv("IS_TESTING_MODE") == "True": # if in testsing mode
    args.env = args.env or "test"
    
if args.env_file:
    # Top priority arg: `env-file`
    dotenv_path = os.path.join(proj_root, args.env_file)
elif args.env in ["prod", ""]:
    # Default to `.env` for running app
    dotenv_path = os.path.join(proj_root, ".env")
else:
    dotenv_path = os.path.join(proj_root, f".env-{args.env}")  

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


