import requests, urllib3, datetime as dt
import pymongo, pprint, json
from pymongo import MongoClient
from collections import defaultdict
from config_local import Projects, Settings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

mongo_client = MongoClient('localhost', 27017)
db = mongo_client.project_status
status_coll  = db.daily_status


class JIRA_API:
    ISSUE_STATUS = ['Analyze', 'Review', 'Clarify', 'Verify', 'Submit', 'Draft', 'Closed']

    def __init__(self, session_id):
        self.session_id = session_id

    def _get_issues_by_filter(self, filter_uri):
        resp = requests.get(filter_uri,
                            cookies={"JSESSIONID": self.session_id},
                            verify=False)
        if resp.status_code == 200:
            return resp.json()
        return None

    def _days_hours_minutes(self, td):
        return td.days, td.seconds // 3600, (td.seconds // 60) % 60

    def _compare_time_start_end(self, delta):
        sec, min, hour, day = delta
        current_time = dt.datetime.now()
        start_time = current_time - dt.timedelta(seconds=sec, minutes=min, hours=hour, days=day)
        end_time = start_time + dt.timedelta(hours=1)
        return start_time, end_time


    def get_issues_by_project(self, project_uri, project_name):
        resp_result = self._get_issues_by_filter(project_uri)
        result = None
        error = True
        if resp_result:
            total = resp_result.get('total')
            defects = resp_result.get('issues')

            results = defaultdict(list)
            for defect in defects:
                key = defect.get('key')
                fields = defect.get('fields')
                project = fields.get('customfield_19501').get('value')
                status = fields.get('status').get('name')
                try:
                    severity = fields.get('customfield_10005').get('value')
                except Exception as e:
                    severity = '2 - Medium'
                reporter = fields.get('reporter').get('displayName')
                try:
                    submit_date = fields.get('customfield_19037').split('T')[0]
                except Exception as e:
                    submit_date = None

                create_date = fields.get('created').split('T')[0]
                results[status].append({'key': key,
                                        'project': project,
                                        'status': status,
                                        'severity': severity,
                                        'reporter': reporter,
                                        'submit_date': submit_date,
                                        'create_date': create_date})
            stats = defaultdict(int)
            for status, issue_list in results.items():
                results[status].sort(key=lambda x: x.get('severity'))
                # Create stats report
                stats[status] = str(len(issue_list))
                stats['total'] += len(issue_list)
            result = {'total': str(total), 'result': results, 'stats': stats, 'project': project_name}
            error = False
        return result, error

    def report_to_send(self, project_uri, project_name,
                       compare_with_record_n_sec_min_hour_day_ago=(15, 0, 0, 0),
                       save_to_db_every_n_hours=1):
        realtime_issues, error = self.get_issues_by_project(project_uri, project_name)
        # Add timestamp
        realtime_issues.update({'date': dt.datetime.now()})

        # Last time it run db save
        latest_saved_record = status_coll.find_one({'project': project_name},
                                                   sort=[('_id', pymongo.DESCENDING)])
        if not latest_saved_record:
            # DB does not have any record, then save it as the first.
            status_coll.insert_one(realtime_issues)
        else:
            # If the record exists in db, pull the time it was saved.
            last_time_db_save = latest_saved_record.get('date')

            # Save the update every `save_to_db_every_n_hours` hour
            db_save_delta_time = dt.datetime.now() - last_time_db_save
            _, hr, _ = self._days_hours_minutes(db_save_delta_time)
            if hr > save_to_db_every_n_hours:
                # Update with the latest record
                status_coll.insert_one(realtime_issues)

        # Generate the report
        if not error:
            # Pull the record of `compare_with_record_n_hours_ago` hour ago
            start_time, end_time = self._compare_time_start_end(delta=compare_with_record_n_sec_min_hour_day_ago)
            latest_compare_record = status_coll.find_one({'project': project_name,
                                                          'date': {'$lt':  end_time,
                                                                   '$gte': start_time }
                                                          },
                                                         sort=[('_id', pymongo.DESCENDING)])
            arrow = ""
            if not latest_compare_record:
                # The first record
                realtime_stats = realtime_issues.get('stats')
                status_report = dict()
                for status in self.ISSUE_STATUS:
                    report_str = f"{status}: {realtime_stats.get(status, '0')} "
                    status_report[status] = report_str

                status_report['total'] = f'{realtime_issues.get("total", "0")}'
            else:
                # Existing record
                realtime_stats = realtime_issues.get('stats')
                record_stats = latest_compare_record.get('stats')
                status_report = dict()

                for status in self.ISSUE_STATUS:
                    dlt_cnt = int(realtime_stats.get(status, 0)) - int(record_stats.get(status, 0))
                    if dlt_cnt > 0:
                        arrow = '↑'
                    elif dlt_cnt < 0:
                        arrow = '↓'
                    report_str = f"{status}: {realtime_stats.get(status, '0')}{arrow}({dlt_cnt}) " if arrow else f"{status}: {realtime_stats.get(status, '0')} "
                    status_report[status] = report_str
                    # Clear arrow
                    arrow = ""

                # Total account
                tlt_dlt_cnt = int(realtime_stats.get('total', 0)) - int(record_stats.get('total', 0))
                if tlt_dlt_cnt > 0:
                    arrow = '↑'
                elif tlt_dlt_cnt < 0:
                    arrow = '↓'
                status_report['total'] = f'{realtime_issues.get("total", "0")}, {arrow}{tlt_dlt_cnt}' if arrow else f'{realtime_issues.get("total", "0")}'

            # Put together the report strings
            result_strings = dict()
            result_strings['draft_and_submit'] = status_report['Draft'] + status_report['Submit']
            result_strings['analyze_and_clarify'] = status_report['Analyze'] + status_report['Clarify']
            result_strings['review_and_verify'] = status_report['Review'] + status_report['Verify'] + status_report['Closed']
            result_strings['total'] = status_report['total']

            # print(f"Project => {project_name}")
            # pprint.pprint(result_strings)
            return result_strings, False
        return None, True


def pull_reports(JESSION_id,
                 compare_with_record_n_sec_min_hour_day_ago,
                 save_to_db_every_n_hours):
    """
    Pull the reports via JIRA API and return the results of a list of dicts. dict(key=project_name, value=report)
    :param JESSION_id:
    :param compare_with_record_n_sec_min_hour_day_ago:
    :param save_to_db_every_n_hours:
    :return:
    """

    api = JIRA_API(JESSION_id)
    errors = False
    reports = list()
    for vendor, projects in Projects.VENDOR_PROJECTS.items():
        for project in projects:
            pull_uri = Settings.JIRA_PROJECT_API_URI(vendor=vendor, project=project)
            report, error = api.report_to_send(pull_uri, project, compare_with_record_n_sec_min_hour_day_ago, save_to_db_every_n_hours)
            errors = errors and error
            reports.append({project: report})

    data = json.dumps(reports)
    return data, errors