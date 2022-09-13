import json
import click
import os
from jira.client import JIRA as JIRACli
from jira import Issue as IssueCli

BACKEND_LABEL = 'BE'
FRONTEND_LABEL = 'FE'


def is_subtask(issue):
    return issue.raw['fields']['issuetype']['subtask']

def is_not_done(issue):
    return issue.fields.status.raw['name'] != 'Done'

def has_no_subtask(issue):
    return len(issue.raw['fields']['subtasks']) == 0

def has_BE_label(issue):
    return any(l for l in issue.fields.labels if l == BACKEND_LABEL)

def has_FE_label(issue):
    return any(l for l in issue.fields.labels if l == FRONTEND_LABEL)

def pretty(issue):
    return '{} : {} [{}/{}]'.format(issue.key, issue.fields.summary, issue.fields.issuetype, issue.fields.status)

def get_csv(issue):
    return '{},{},{},{}'.format(issue.key, issue.fields.summary, issue.fields.issuetype, issue.fields.status)

def print_issue(issue):
    print(pretty(issue))

def print_json(issue):
    json_object = json.dumps(issue.raw, indent=4)
    print(json_object)

class Jira:
    def __init__(self, token: str, project: str):
        self.__jira = JIRACli(server='https://jira.deliveryhero.com/', token_auth=token)
        self.__project = project

    def get_jira(self):
        return self.__jira

    def get_all_issues(self, user_name):
        return self.__jira.search_issues(f"project={self.__project} and (assignee was '{user_name}') and status = Done")

    def get_current_sprint_issues(self, status: str = ''):
        jql = f'project={self.__project} and sprint in openSprints() '
        if len(status) > 0:
            jql = f'project={self.__project} and sprint in openSprints() and status = "{status}"'
        return self.__jira.search_issues(jql)

    def get_current_sprint_open_issues(self):
        return self.__jira.search_issues(f'project={self.__project} and sprint in openSprints() and status != Done')

    def get_current_sprint_subtask_open_issues(self):
        ''' subtask which are not done'''
        return [issue for issue in self.get_current_sprint_issues() if is_subtask(issue) and is_not_done(issue)]

    def get_current_sprint_open_issues_without_subtask(self):
        return [issue for issue in self.get_current_sprint_issues() if has_no_subtask(issue) and not is_subtask(issue)]


def print_fields(values: str):
    # print(values)
    for v in values:
        v = v.replace(", ", " ")
        d = v[v.find("[") + 1:v.find("]")]
        res = dict(item.split("=") for item in d.split(","))
    return res

def fetch_all_tickets():
    token = os.getenv('JIRA_API_TOKEN', '')
    be_user_name = os.getenv('DEFAULT_BACKEND_USER_NAME')
    project_id = os.getenv('PROJECT_ID')
    jira= Jira(token, project_id)

    issues = jira.get_all_issues(be_user_name)

    for issue in issues:
        sprint = print_fields(issue.raw['fields']['customfield_10621'])
        story_point = issue.raw['fields']['customfield_10013'] if 'customfield_10013' in issue.raw['fields'] else '-'
        print('{},{},{}'.format(get_csv(issue), sprint['name'], story_point))



if __name__ == '__main__':
    token = os.getenv('JIRA_API_TOKEN', '')
    fe_user_name = os.getenv('DEFAULT_FRONTEND_USER_NAME')
    project_id = os.getenv('PROJECT_ID')
    jira= Jira(token, project_id)

    issues = jira.get_current_sprint_open_issues()


    for issue in issues:
        if is_subtask(issue):
            continue
        if not has_no_subtask(issue):
            print(f'{issue.key} already have subtask')
            continue

        issue_dict = {
                'project': {'key': project_id},
                # 'summary': '',
                'description': '',
                'issuetype': {'name': 'Sub-task'},
                'parent': {'key': issue.key}
        }

        if has_BE_label(issue) and has_FE_label(issue):
            # create api agreement subtask
            issue_dict['summary'] = 'BE API Agreement'
            api_issue = jira.get_jira().create_issue(fields=issue_dict)
            print('created API Agreement ', api_issue.key, ' subtask for ', issue.key)

            # create backend subtask
            issue_dict['summary'] = BACKEND_LABEL
            be_issue = jira.get_jira().create_issue(fields=issue_dict)
            print('created BE ', be_issue.key, ' subtask for ', issue.key)

        if has_FE_label(issue):
            # create frontend subtask
            issue_dict['summary'] = FRONTEND_LABEL
            fe_issue = jira.get_jira().create_issue(fields=issue_dict)
            fe_issue.update(assignee={'name': fe_user_name})
            print('created FE ', fe_issue.key, ' subtask for ', issue.key)
