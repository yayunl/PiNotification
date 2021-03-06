# Run this app in the laptop.
import socket, pprint as pp
import time, re
from utils import pull_reports
from ssh_operation import SSH_Connection
from config_local import Settings, Projects


def server_started_on_pi():

    ssh = SSH_Connection(Settings.TARGET_SERVER_IP, user='pi', passw='pi')
    netstat_cmd = 'sudo netstat -tupln | grep 0.0.0.0:12333'
    if ssh.connect():
        ssh_ch = ssh.invoke_shell()
        out, err = ssh.send(ssh_ch, netstat_cmd)
        process = None
        if not err:
            try:
                regex = r'.* LISTEN.*?([0-9]+)'
                process = re.findall(regex, out, re.MULTILINE)[0]
                # process_num = process.split('/')[0]
            except:
                pass

            if process:
                kill_cmd = f'kill -9 {process}'
                print(f"Attempt kill the process with cmd => {kill_cmd}")
                out, err = ssh.send(ssh_ch, kill_cmd)

            print("Starting the server on Pi 4...")
            out, err = ssh.send(ssh_ch, 'nohup ./socket_server/run_socket_server.sh $> ./socket_server/runlog.txt')

            if not err:
                return True

    return False


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
    if server_started_on_pi():

        # Make sure you have the updated jession id.
        print("Make sure you have the updated jession id.")
        flash_interval = input(f"Refresh interval in secs. (>= 15s) (default {Settings.REPORT_REFLASH_INTERVAL_IN_SECS}s): ")
        try:
            flash_interval = int(flash_interval)
        except:
            print("Invalid refresh interval. Must be a integer. Use default instead.")
            flash_interval = Settings.REPORT_REFLASH_INTERVAL_IN_SECS


        # Prompt for inputs
        jession_id=input("JESSION ID: ") or Settings.JESSION_ID

        compare_with_record_of_time_ago_raw = input(f"Compare with the record of (secs,mins,hours,days) ago. Default is {Settings.COMPARE_WITH_RECORD_OF_N_HOUR_AGO}: ")

        # Run
        if compare_with_record_of_time_ago_raw:
            compare_with_record_of_time_ago_input = [int(t.strip('')) for t in compare_with_record_of_time_ago_raw.split(',')]
        else:
            compare_with_record_of_time_ago_input = Settings.COMPARE_WITH_RECORD_OF_N_HOUR_AGO

        run(jession_id, compare_with_record_of_time_ago_input, flash_interval)

    print("Please make sure the remote server on Pi starts before running the client app.")

