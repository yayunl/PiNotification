# Run this app in the laptop.
import socket, pprint as pp
import time
from utils import pull_reports
from ssh_operation import SSH_Connection
from config_local import Settings, Projects


def start_server_on_pi():

    ssh = SSH_Connection(Settings.TARGET_SERVER_IP, user='pi', passw='pi')
    if ssh.connect():
        ssh_ch = ssh.invoke_shell()
        out, err = ssh.send(ssh_ch, 'nohup ./socket_server/run_socket_server.sh')
        print(out)
    print("Server started on pi.")


def run(jession_id, compare_record_interval, flash_interval):
    # Pull the first report
    data, error = pull_reports(JESSION_id=jession_id,
                               compare_with_record_n_sec_min_hour_day_ago=compare_record_interval,
                               save_to_db_every_n_hours=1)
    if not error:
        # Socket connection info
        host = Settings.TARGET_SERVER_IP
        port = Settings.TARGET_SERVER_PORT

        # decoded_d = json.load(bdata)
        # print(decoded_d)
        t1 = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            time.sleep(3)
            # Send the first report
            s.sendall(bytes(data, encoding='utf-8'))

            while True:

                timer = time.time() - t1
                if timer > int(flash_interval):
                    t1 = time.time()  # Reset timer
                    # Pull the reports
                    data, error = pull_reports(JESSION_id=jession_id,
                                               compare_with_record_n_sec_min_hour_day_ago=compare_record_interval,
                                               save_to_db_every_n_hours=1)
                    if not error:
                        print("Send a new report...")
                        pp.pprint(data)
                        s.sendall(bytes(data, encoding='utf-8'))

            # time.sleep(3)
            # s.sendall(b'bye')
    else:
        print("Failed to pull report from JIRA. Make sure you have the updated jession id.")


if __name__ == '__main__':
    # Start the sever side application first.
    start_server_on_pi()

    # Make sure you have the updated jession id.
    print("Make sure you have the updated jession id.")
    flash_interval = input("Refresh interval in secs. (>= 15s) (default 15s): ")
    try:
        flash_interval = int(flash_interval)
    except:
        print("Invalid refresh interval. Must be a integer. Use default instead.")
        flash_interval = Settings.REPORT_REFLASH_INTERVAL_IN_SECS


    # Prompt for inputs
    jession_id=input("JESSION ID: ") or Settings.JESSION_ID

    compare_with_record_of_time_ago_raw = input("Compare with the record of (secs,mins,hours,days) ago. Default is 1 day (0,0,0,1) ago: ")

    # Run
    if compare_with_record_of_time_ago_raw:
        compare_with_record_of_time_ago_input = [int(t.strip('')) for t in compare_with_record_of_time_ago_raw.split(',')]
    else:
        compare_with_record_of_time_ago_input = Settings.COMPARE_WITH_RECORD_OF_N_HOUR_AGO

    run(jession_id, compare_with_record_of_time_ago_input, flash_interval)


