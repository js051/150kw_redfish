from werkzeug.security import generate_password_hash
from mylib.models.account_model import RoleModel, AccountModel
from mylib.models.setting_model import SettingModel
import sqlalchemy as sa
from load_env import redfish_info
from mylib.db.extensions import ext_engine


def init_orm(app, db):
    """
    Initialize the ORM models and create the database tables if they don't exist.
    
    Args:
        app: The Flask application instance.
        db: The SQLAlchemy instance.
    """
    def ensure_setting(key, value):
        setting = SettingModel.query.filter_by(key=key).first()
        if not setting:
            setting = SettingModel(key=key, value=value)
            db.session.add(setting)
            db.session.commit()
        elif setting.value != str(value):
            setting.value = str(value)
            db.session.commit()
        return setting
 
    def key_ensure_setting(key, value):
        setting = SettingModel.query.filter_by(key=key).first()
        if not setting:
            setting = SettingModel(key=key, value=value)
            db.session.add(setting)
            db.session.commit()
        return setting

    def check_db_schema_changes(db):
        """Check if database schema has changed and needs migration"""
        try:
            current_metadata = sa.MetaData()
            current_metadata.reflect(bind=db.engine)
            expected_metadata = db.metadata
            for table_name in expected_metadata.tables:
                if table_name not in current_metadata.tables:
                    return True
                current_table = current_metadata.tables[table_name]
                expected_table = expected_metadata.tables[table_name]
                current_columns = set(c.name for c in current_table.columns)
                expected_columns = set(c.name for c in expected_table.columns)
                if current_columns != expected_columns:
                    return True
            return False
        except Exception as e:
            return False
    try:
        with app.app_context():
            # @see https://flask-sqlalchemy.readthedocs.io/en/stable/queries/
            # Recreate database if schema has changed
            if check_db_schema_changes(db):
                print(" * Database schema has changed. Recreating tables...")
                db.drop_all()
            db.create_all()
            # Create default roles
            if not RoleModel.query.first():  # Check if any role exists
                admin_privi = ["Login",
                            "ConfigureManager",
                            "ConfigureUsers",
                            "ConfigureSelf",
                            "ConfigureComponents",
                            ]
                operator_privi = ["Login",
                                "ConfigureComponents",
                                "ConfigureSelf"
                                ]
                readonly_privi = ["Login",
                                "ConfigureSelf"
                                ]
                admin_role = RoleModel(name='Administrator', assigned_privileges=",".join(admin_privi))

                operator_role = RoleModel(name='Operator', assigned_privileges=",".join(operator_privi))
                readonly_role = RoleModel(name='ReadOnly', assigned_privileges=",".join(readonly_privi))
                noaccess_role = RoleModel(name='NoAccess', assigned_privileges="")
                db.session.add(admin_role)
                db.session.add(operator_role)
                db.session.add(readonly_role)
                db.session.add(noaccess_role)
                db.session.commit()

            # Create default users
            admin_role = RoleModel.query.filter_by(name='Administrator').first()
            if not admin_role:
                raise Exception("Administrator role not found. Please ensure roles are created before users.")

            admin_password="scrypt:32768:8:1$rruxhcJwq52Ewfef$eda449a98ba19f627d982ab62ea345b945ff671555e96318b78534b7f0bcdc4f494b107beeb7578174b0d58828347b3e3eb732558035a0ecd706729c781a0be1"
            root_password="scrypt:32768:8:1$ZCCvE9TykaVhArpW$9b408f1d1eccc99fff064ad4052eabd6737d33174fdf61f5d19fe2c5ac5f5978243ccb69fd4fe31aeb13beb1e786c20ead5d945e82b4ae914d22a3d2b0cb7d33"
            superuser_password="scrypt:32768:8:1$4muYEoJRQ6ajfqvO$7a1a983e81b2ddf0dcfcf9f49bb3471671f029dcf9f93aeec4f6e2fa698673f9a0cd533498d23051bc84cc175bb11ee7e6384588a5c5f4773af0fd6b18d00ad5"
            create_users =[
                {
                    "user_name": "admin",
                    "password": admin_password
                },
                {
                    "user_name": "root",
                    "password": root_password
                },
                {
                    "user_name": "superuser",
                    "password": superuser_password
                }
            ]
            for user in create_users:
                existing_user = AccountModel.query.filter_by(user_name=user['user_name']).first()
                if not existing_user:
                    new_user = AccountModel(user_name=user['user_name'], role=admin_role, password=user['password'])
                    db.session.add(new_user)
                    db.session.commit()
                else:
                    if existing_user.password != user['password']:
                        existing_user.password = user['password']
                    if existing_user.role != admin_role:
                        existing_user.role = admin_role
                    db.session.commit()
            #AccountService DSP0246
            ensure_setting(key='AccountService.MaxAllowedAccounts', value='15')
            key_ensure_setting(key='AccountService.AuthFailureLoggingThreshold', value='3')
            key_ensure_setting(key='AccountService.MinPasswordLength', value='5')
            key_ensure_setting(key='AccountService.MaxPasswordLength', value='25')
            key_ensure_setting(key='AccountService.AccountLockoutThreshold', value='3')
            key_ensure_setting(key='AccountService.AccountLockoutDuration', value='60')
            key_ensure_setting(key='AccountService.AccountLockoutCounterResetAfter', value='30')
            key_ensure_setting(key='SessionService.SessionTimeout', value='360')
            
            ##
            # Ensure "key" of default settings exists in db.
            ##
            # # EventService 
            # key_ensure_setting(key='EventService.DeliveryRetryAttempts', value='3')
            # key_ensure_setting(key='EventService.DeliveryRetryIntervalSeconds', value='60')
            # key_ensure_setting(key='EventService.Destination', value='127.0.0.1')
            # key_ensure_setting(key='EventService.TrapCommunity', value='public')
            # key_ensure_setting(key='EventService.ServiceEnabled', value='1')
            # # Managers
            # key_ensure_setting(key='Managers.SNMP.ProtocolEnabled', value='0')
            # key_ensure_setting(key='Managers.SNMP.Port', value='9000')
            # key_ensure_setting(key='Managers.NTP.NTPServer', value='ntp.ubuntu.com')
            # key_ensure_setting(key='Managers.NTP.ProtocolEnabled', value='1')
            # key_ensure_setting(key='Managers.NTP.Port', value='123')
            # key_ensure_setting(key='Managers.ServiceIdentification', value='ServiceRoot')
            if redfish_info.get('Settings'):
                for setting in redfish_info.get('Settings', {}).get('DefaultValues', []):
                    try:
                        k = setting.get('key')
                        v = str(setting.get('value'))
                        print(f"  - Check Setting: key={k}, value={v}")
                        if k and v:
                            print(f"    Ensure Setting: key={k}, value={v}")
                            key_ensure_setting(key=k, value=v)
                    except Exception as e:
                        print(f"  - Check Setting FAIL: setting={setting}")

            
            
    except Exception as e:
            print(f" * Error occurred: {e}")
    return



def reset_to_defaults():
    try:    
        print(f"Reset to default starting ...")
        
        db = ext_engine.get_db()
        
        print(f"  + Drop all tables ...")
        db.drop_all()
        print(f"    Drop all tables completed.")
        
        print(f"  + Init sqlite tables ...")
        init_orm(ext_engine.get_app(), db)
        print(f"    Init sqlite tables completed.")

        print(f"Reset to default completed.")
        return True
    except Exception as e:
        print(f"Reset to default failed: {e}")
        return False