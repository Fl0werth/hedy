import requests
import json
import random
from utils import timems
import urllib.parse
from config import config
import sys
import threading
import re
from app import app
from flask import Flask, request as flaskRequest, current_app

with app.app_context():
    current_app.name
# USAGE: python e2e_tests.py [CONCURRENT_TESTS] [alpha|test]
# Concurrent tests are a way to stress test an environment
# When no environment is specified, the tests are run against localhost

import argparse

args = argparse.ArgumentParser()
args.add_argument('--concurrent', help='how many tests to run at the same time (stress testing), default is 1',
                  type=int)
args.add_argument('--host', help='Host against which to run the tests (optional), default is localhost')
args.add_argument('--endpoint',
                  help='Endpoint against which to run the tests (optional, by default \'--host\' is used)')
args = args.parse_args()

host = 'http://localhost:' + str(config['port']) + '/'
hosts = {'alpha': 'https://hedy-alpha.herokuapp.com/', 'test': 'https://hedy-test.herokuapp.com/'}

if args.endpoint:
    host = args.endpoint

elif args.host:
    if not args.host in hosts:
        raise Exception('No such host')
    host = hosts[sys.argv[2]]


# test structure: [tag, method, path, headers, body, code, after_test_function]
def request(state, test, counter, username):
    start = timems()

    if isinstance(threading.current_thread(), threading._MainThread):
        print('Start #' + str(counter) + ': ' + test[0])

    # If path, headers or body are functions, invoke them passing them the current state
    if callable(test[2]):
        test[2] = test[2](state)

    if callable(test[3]):
        test[3] = test[3](state)

    if callable(test[4]):
        test[4] = test[4](state)

    # If no explicit cookie passed, use the one from the state
    if not 'cookie' in test[3] and 'cookie' in state['headers']:
        test[3]['cookie'] = state['headers']['cookie']

    if isinstance(test[4], dict):
        test[3]['content-type'] = 'application/json'
        test[4] = json.dumps(test[4])

    # We pass the X-Testing header to let the server know that this is a request coming from an E2E test, thus no transactional emails should be sent.
    test[3]['X-Testing'] = '1'

    r = getattr(requests, test[1])(host + test[2], headers=test[3], data=test[4])

    if 'Content-Type' in r.headers and r.headers['Content-Type'] == 'application/json':
        body = r.json()
    else:
        body = r.text

    if r.history and r.history[0]:
        # This will be the case if there's a redirect
        code = r.history[0].status_code
        headers = r.history[0].headers
        if getattr(r.history[0], '_content'):
            body = getattr(r.history[0], '_content').decode('utf-8')
    else:
        code = r.status_code

    output = {
        'code': code,
        'headers': r.headers,
        'body': body
    }

    if (code != test[5]):
        print(output)
        raise Exception('A test failed!')

    if len(test) == 7:
        test[6](state, output, username)

    if isinstance(threading.current_thread(), threading._MainThread):
        print('Done  #' + str(counter) + ': ' + test[0] + ' - ' + str(r.status_code) + ' (' + str(
            timems() - start) + 'ms)')

    return output


def run_suite(suite):
    # We use a random username so that if a test fails, we don't have to do a cleaning of the DB so that the test suite can run again
    # This also allows us to run concurrent tests without having username conflicts.
    username = 'user' + str(random.randint(10000, 100000))
    tests = suite(username)
    state = {'headers': {}}
    t0 = timems()

    if not isinstance(tests, list):
        return print('Invalid test suite, must be a list.')
    counter = 1

    def run_test(test, counter):
        result = request(state, test, counter, username)

    for test in tests:
        # If test is nested, run a nested loop
        if not (isinstance(test[0], str)):
            for subtest in test:
                run_test(subtest, counter)
                counter += 1
        else:
            run_test(test, counter)
            counter += 1

    if isinstance(threading.current_thread(), threading._MainThread):
        print('Test suite successful! (' + str(timems() - t0) + 'ms)')
    else:
        return timems() - t0


def invalidMap(tag, method, path, bodies):
    output = []
    counter = 1
    for body in bodies:
        output.append(['invalid ' + tag + ' #' + str(counter), method, path, {}, body, 400])
        counter += 1
    return output


# We define after_test_functions here because multiline lambdas are not supported by python
def setSentCookies(state, response, username):
    if 'Set-Cookie' in response['headers']:
        state['headers']['cookie'] = response['headers']['Set-Cookie']


def successfulSignup(state, response, username):
    if not 'token' in response['body']:
        raise Exception('No token present')
    state['token'] = response['body']['token']
    setSentCookies(state, response, username)


def successfulSignupTeacher(state, response, username):
    state['teacher-session'] = response['headers']['Set-Cookie']
    setSentCookies(state, response, username)


def successfulSignupStudent(state, response, username):
    state['student-session'] = response['headers']['Set-Cookie']


def getProfile1(state, response, username):
    profile = response['body']
    if profile['username'] != username:
        raise Exception('Invalid username (getProfile1)')
    if profile['email'] != username + '@e2e-testing.com':
        raise Exception('Invalid username (getProfile1)')
    if not profile['session_expires_at']:
        raise Exception('No session_expires_at (getProfile1)')
    expire = profile['session_expires_at'] - config['session']['session_length'] * 60 * 1000 - timems()
    if expire > 0:
        raise Exception('Invalid session_expires_at (getProfile1), too large')
    # We give the server up to 2s to respond to the query
    if expire < -2000:
        raise Exception('Invalid session_expires_at (getProfile1), too small')


def getProfile2(state, response, username):
    profile = response['body']
    if profile['country'] != 'NL':
        raise Exception('Invalid country (getProfile2)')
    if profile['email'] != username + '@e2e-testing2.com':
        raise Exception('Invalid country (getProfile2)')
    if not 'verification_pending' in profile or profile['verification_pending'] != True:
        raise Exception('Invalid verification_pending (getProfile2)')


def getProfile3(state, response, username):
    profile = response['body']
    if 'verification_pending' in profile:
        raise Exception('Invalid verification_pending (getProfile3)')


def getProfile4(state, response, username):
    profile = response['body']
    if not 'verification_pending' in profile or profile['verification_pending'] != True:
        raise Exception('Invalid verification_pending (getProfile4)')
    if not 'prog_experience' in profile or profile['prog_experience'] != 'yes':
        raise Exception('Invalid prog_experience (getProfile4)')
    if not 'experience_languages' in profile or not isinstance(profile['experience_languages'], list) or len(
            profile['experience_languages']) != 1 or profile['experience_languages'][0] != 'python':
        raise Exception('Invalid experience_languages (getProfile4)')


def getProfile5(state, response, username):
    profile = response['body']
    if not 'prog_experience' in profile or profile['prog_experience'] != 'no':
        raise Exception('Invalid prog_experience (getProfile5)')
    if not 'experience_languages' in profile or not isinstance(profile['experience_languages'], list) or len(
            profile['experience_languages']) != 2 or profile['experience_languages'][0] not in ['scratch',
                                                                                                'other_text'] or \
            profile['experience_languages'][1] not in ['scratch', 'other_text']:
        raise Exception('Invalid experience_languages (getProfile5)')


def emailChange(state, response, username):
    if not isinstance(response['body']['token'], str):
        raise Exception('Invalid country (emailChange)')
    if response['body']['username'] != username:
        raise Exception('Invalid username (emailChange)')
    state['token2'] = response['body']['token']


def recoverPassword(state, response, username):
    if not 'token' in response['body']:
        raise Exception('No token present')
    state['token'] = response['body']['token']


def checkMainSessionVars(state, response, username):
    if not 'session_id' in response['body']['session']:
        raise Exception('No session_id set')
    if not 'proxy_enabled' in response['body']:
        raise Exception('No proxy_enabled variable set')
    state['session_id'] = response['body']['session']['session_id']
    state['proxy_enabled'] = response['body']['proxy_enabled']
    setSentCookies(state, response, username)


def checkTestSessionVars(state, response, username):
    # If proxying to test is disabled, there is nothing to do.
    if not state['proxy_enabled']:
        return
    if not 'session_id' in response['body']['session']:
        raise Exception('No session_id set')
    if not 'test_session' in response['body']['session']:
        raise Exception('No test_session set')
    if response['body']['session']['session_id'] != state['session_id']:
        raise Exception('session_id from main not passed to test')
    state['test_session'] = response['body']['session']['test_session']
    setSentCookies(state, response, username)


def checkMainSessionVarsAgain(state, response, username):
    if not 'session_id' in response['body']['session']:
        raise Exception('No session_id set')
    if response['body']['session']['session_id'] != state['session_id']:
        raise Exception('session_id from main not maintained after proxying to test')
    # If proxying to test is disabled, there is nothing else to do.
    if not state['proxy_enabled']:
        return
    if not 'test_session' in response['body']['session']:
        raise Exception('No test_session set')
    if response['body']['session']['test_session'] != state['test_session']:
        raise Exception('test_session not received by main')


def retrieveProgramsBefore(state, response, username):
    if not isinstance(response['body'], dict):
        raise Exception('Invalid response body')
    if not 'programs' in response['body'] or not isinstance(response['body']['programs'], list):
        raise Exception('Invalid programs list')
    if len(response['body']['programs']) != 0:
        raise Exception('Programs list should be empty')


def retrieveProgramsAfter(state, response, username):
    if not isinstance(response['body'], dict):
        raise Exception('Invalid response body')
    if not 'programs' in response['body'] or not isinstance(response['body']['programs'], list):
        raise Exception('Invalid programs list')
    if len(response['body']['programs']) != 1:
        raise Exception('Programs list should contain one program')
    program = response['body']['programs'][0]
    state['program'] = program
    if not isinstance(program, dict):
        raise Exception('Invalid program type')
    if not 'code' in program or program['code'] != 'print Hello world':
        raise Exception('Invalid program.code')
    if not 'level' in program or program['level'] != 1:
        raise Exception('Invalid program.level')


def getTeacherClasses1(state, response, username):
    if not isinstance(response['body'], list):
        raise Exception('Classes should be a list')
    if len(response['body']) != 0:
        raise Exception('Classes should be empty')


def getTeacherClasses2(state, response, username):
    if len(response['body']) != 1:
        raise Exception('Classes should contain one class')
    Class = response['body'][0]
    if not isinstance(Class.get('date'), int):
        raise Exception('Class should contain date')
    if not isinstance(Class.get('id'), str):
        raise Exception('Class should contain id')
    if not isinstance(Class.get('link'), str):
        raise Exception('Class should contain link')
    if Class.get('name') != 'class1':
        raise Exception('Invalid class name')
    if not isinstance(Class.get('students'), list):
        raise Exception('Class should contain a list of students')
    if len(Class.get('students')) != 0:
        raise Exception('Student list should be empty')
    if Class.get('teacher') != 'teacher-' + username:
        raise Exception('Invalid teacher')

    state['classes'] = response['body']


def getClass1(state, response, username):
    Class = response['body']
    if not isinstance(Class, dict):
        raise Exception('Invalid response body')
    if not isinstance(Class.get('link'), str):
        raise Exception('Class should contain link')
    if not isinstance(Class.get('id'), str):
        raise Exception('Class should contain id')
    if Class.get('name') != 'class1':
        raise Exception('Invalid class name')
    if not isinstance(Class.get('students'), list):
        raise Exception('Class should contain a list of students')
    if len(Class.get('students')) != 0:
        raise Exception('Student list should be empty')


def getTeacherClasses3(state, response, username):
    Class = response['body'][0]
    if Class.get('name') != 'class_renamed':
        raise Exception('Invalid class name')


def getClass2(state, response, username):
    Class = response['body']
    if Class.get('name') != 'class_renamed':
        raise Exception('Invalid class name')


def redirectAfterJoin1(state, response, username):
    if not re.search('http://localhost:\d\d\d\d/my-profile', response['body']):
        raise Exception('Invalid redirect')


def createPublicProgram(state, response, username):
    state['public_program'] = response['body']['id']


def getStudentClasses1(state, response, username):
    classes = response['body'].get('student_classes')
    if not isinstance(classes, list):
        raise Exception('Invalid classes list')
    if len(classes) != 1:
        raise Exception('Class list should contain one item')
    Class = classes[0]
    if not isinstance(Class, dict):
        raise Exception('Invalid class')
    if Class['id'] != state['classes'][0]['id']:
        raise Exception('Invalid class id')
    if Class['name'] != 'class_renamed':
        raise Exception('Invalid class name')
    if len(Class.keys()) != 2:
        raise Exception('Too many fields contained in class')


def getClass3(state, response, username):
    students = response['body'].get('students')
    if len(students) != 1:
        raise Exception('Student list should contain one student')
    student = students[0]
    state['student'] = student
    if student.get('highest_level') != 0:
        raise Exception('student.highest_level should be 0')
    if student.get('programs') != 0:
        raise Exception('student.programs should be 0')
    if student.get('latest_shared') != None:
        raise Exception('student.latest_shared should be None')
    if not isinstance(student.get('last_login'), str):
        raise Exception('student.last_login should be a string')
    if student.get('username') != 'student-' + username:
        raise Exception('Invalid student username')


def getClass4(state, response, username):
    student = response['body'].get('students')[0]
    if student.get('highest_level') != 1:
        raise Exception('student.highest_level should be 0')
    if student.get('programs') != 2:
        raise Exception('student.programs should be 2')
    if not isinstance(student.get('latest_shared'), dict):
        raise Exception('student.latest_shared should be a list')
    if student.get('latest_shared').get('name') != 'Public program 1':
        raise Exception('student.latest_shared.name should be "Public program 1"')
    link = student.get('latest_shared').get('link')
    if not re.search('http://localhost:\d\d\d\d/hedy/' + state['public_program'] + '/view', link):
        raise Exception('Invalid student.latest_shared.link ' + link + ', expecting',
                        'http://localhost:\d\d\d\d/hedy/' + state['public_program'] + '/view')


def getTeacherClasses4(state, response, username):
    Class = response['body'][0]
    if len(Class.get('students')) != 1:
        raise Exception('Student list should contain a student id')
    if Class.get('students')[0] != 'student-' + username:
        raise Exception('Invalid student username')


def getStudentClasses2(state, response, username):
    classes = response['body'].get('student_classes')
    if not isinstance(classes, list):
        raise Exception('Invalid classes list')
    if len(classes) != 0:
        raise Exception('Class list should be empty')


def checkJoinLink(state, response, username):
    if not re.search(
            'http://localhost:\d\d\d\d/class/' + state['classes'][0]['id'] + '/prejoin/' + state['classes'][0]['link'],
            response['body']):
        raise Exception('Invalid redirect')


def testQuiz(tag, tests):

    bodies = tests()
    output = []
    counter = 1
    if config['quiz-enabled']:
        for body in bodies:
            testArray = [tag + ' #' + str(counter) + body[0], body[1], body[2], body[3], body[4], body[5]]
            testArray.append(body[6]) if len(body) == 7 else None
            output.append(testArray)
            counter += 1
        return output
    else:
        output[5] = 404
        return output


def happyFlowTestCasesQuiz():
    return [['get quiz start', 'get', '/quiz/start/1', {}, {}, 200],
            ['get quiz question with valid level', 'get', '/quiz/quiz_questions/1/1/1', {},{}, 200, postQuizFormData],
            ['submit answer of quiz', 'post', '/submit_answer/1/1/1', {}, {'radio_option': '1-B'}, 200, checkQuizSessionVarsAttempt1],
            ['submit answer of quiz', 'post', '/submit_answer/1/1/2', {}, {'radio_option': '1-C'}, 200, checkQuizSessionVarsAttempt2],
            ['submit answer of quiz', 'post', '/submit_answer/1/1/3', {}, {'radio_option': '1-A'}, 200, checkQuizSessionVarsAttempt3],
            ['submit answer of quiz', 'post', '/submit_answer/1/2/1', {}, {'radio_option': '1-A'}, 200, checkQuizSessionVarsQ2Attempt1],
            ['submit answer of quiz', 'post', '/submit_answer/1/2/2', {}, {'radio_option': '1-D'}, 200, checkQuizSessionVarsQ2Attempt2]

            ]



def invalidTestCasesQuiz():
    return [
        ['invalid quiz start', 'get', '/quiz/start/a', {}, {}, 403],
        ['get quiz question with invalid level', 'get', '/quiz/quiz_questions/1000/1/1', {},{}, 404],
        ['submit answer of quiz at invalid level', 'post', '/submit_answer/1000/1/1', {}, {}, 404,
         checkQuizSessionVarsAttempt1],
        ['submit answer of quiz at invalid level', 'post', '/submit_answer/1000/1/1', {}, {}, 404,
         checkQuizSessionVarsAttempt1]
    ]


# def checkSubmittedAnswer(state, response, username):
#     add state variables and request form variables to pass to next endpoint

def postQuizFormData(state, response, correctOption):

    state['radio_option'] = flaskRequest.form["radio_option"]
    if correctOption not in state['radio_option']:
        raise Exception('Chosen answer does not match with the correct answer')
    return

def checkQuizSessionVarsAttempt1(state, response, username):
    postQuizFormData(state,response, "A")
    if not 'quiz-attempt' in response['body']['session']:
        raise Exception('No quiz-attempt variable set')
    if not 'total_score' in response['body']['session']:
        raise Exception('No total_score variable set')
    if not session['correct_answer'] in response['body']['session']:
        raise Exception('No correct answer variable set')
    if config['quiz-max-attempts'] != 4:
        raise Exception('The value of the nr of maximum attempts is invalid')
    if state['quiz-attempt'] != 1:
        raise Exception('Quiz attempt is not 1x')
    if state['total_score'] != 5:
        raise Exception('Total score does not equal 5')
    if state['correct_answer'] != 1:
        raise Exception('Total score does not equal 5')
    state['quiz-attempt'] = response['body']['session']['quiz-attempt']
    state['total_score'] = response['body']['session']['total_score']
    state['correct_answer'] = response['body']['session']['correct_answer']


def checkQuizSessionVarsAttempt2(state, response, username):
    postQuizFormData(state,response, "A")
    if not 'quiz-attempt' in response['body']['session']:
        raise Exception('No quiz-attempt variable set')
    if not 'total_score' in response['body']['session']:
        raise Exception('No total_score variable set')
    if not session['correct_answer'] in response['body']['session']:
        raise Exception('No correct answer variable set')
    if config['quiz-max-attempts'] != 4:
        raise Exception('The value of the nr of maximum attempts is invalid')
    if state['quiz-attempt'] != 2:
        raise Exception('Quiz attempt is not 2x')
    if state['total_score'] != (10 / 3):
        raise Exception('Total score does not equal 10.333')
    if state['correct_answer'] != 1:
        raise Exception('Total score does not equal to 1')

    state['quiz-attempt'] = response['body']['session']['quiz-attempt']
    state['total_score'] = response['body']['session']['total_score']
    state['correct_answer'] = response['body']['session']['correct_answer']


def checkQuizSessionVarsAttempt3(state, response, username):
    postQuizFormData(state,response, "A")
    if not 'quiz-attempt' in response['body']['session']:
        raise Exception('No quiz-attempt variable set')
    if not 'total_score' in response['body']['session']:
        raise Exception('No total_score variable set')
    if not session['correct_answer'] in response['body']['session']:
        raise Exception('No correct answer variable set')
    if config['quiz-max-attempts'] != 4:
        raise Exception('The value of the nr of maximum attempts is invalid')
    if state['quiz-attempt'] != 3:
        raise Exception('Quiz attempt is not 3x')
    if state['total_score'] != (5 / 3):
        raise Exception('Total score does not equal 10.333')
    if state['correct_answer'] != 1:
        raise Exception('Total score does not equal to 1')

    state['quiz-attempt'] = response['body']['session']['quiz-attempt']
    state['total_score'] = response['body']['session']['total_score']
    state['correct_answer'] = response['body']['session']['correct_answer']


def checkQuizSessionVarsQ2Attempt1(state, response, username):
    postQuizFormData(state,response,"D")
    if not 'quiz-attempt' in response['body']['session']:
        raise Exception('No quiz-attempt variable set')
    if not 'total_score' in response['body']['session']:
        raise Exception('No total_score variable set')
    if not session['correct_answer'] in response['body']['session']:
        raise Exception('No correct answer variable set')
    if config['quiz-max-attempts'] != 4:
        raise Exception('The value of the nr of maximum attempts is invalid')
    if state['quiz-attempt'] != 2:
        raise Exception('Quiz attempt is not 3x')
    if state['total_score'] != (5/ 3):
        raise Exception('Total score does not equal to previous score 1.666')
    if state['correct_answer'] != 1:
        raise Exception('Total score does not equal to 1')

    state['quiz-attempt'] = response['body']['session']['quiz-attempt']
    state['total_score'] = response['body']['session']['total_score']
    state['correct_answer'] = response['body']['session']['correct_answer']


def checkQuizSessionVarsQ2Attempt2(state, response, username):
    postQuizFormData(state,response, "D")
    if not 'quiz-attempt' in response['body']['session']:
        raise Exception('No quiz-attempt variable set')
    if not 'total_score' in response['body']['session']:
        raise Exception('No total_score variable set')
    if not session['correct_answer'] in response['body']['session']:
        raise Exception('No correct answer variable set')
    if config['quiz-max-attempts'] != 4:
        raise Exception('The value of the nr of maximum attempts is invalid')
    if state['quiz-attempt'] != 3:
        raise Exception('Quiz attempt is not 2x')
    if state['total_score'] != (20 / 3):
        raise Exception('Total score does not equal 6.6666')
    if state['correct_answer'] != 2:
        raise Exception('Total score does not equal to 2')

    state['quiz-attempt'] = response['body']['session']['quiz-attempt']
    state['total_score'] = response['body']['session']['total_score']
    state['correct_answer'] = response['body']['session']['correct_answer']


def suite (username):
    return [
        # Session variables
        ['get session vars from main', 'get', '/session_main', {}, {}, 200, checkMainSessionVars],
        ['get session vars from test', 'get', '/session_test', {}, {}, 200, checkTestSessionVars],
        ['get session vars from main again', 'get', '/session_main', {}, {}, 200, checkMainSessionVarsAgain],
        # Main page
        ['get root', 'get', '/', {}, '', 200],
        # Admin page
        ['get admin', 'get', '/admin', {}, {}, 200],
        # Auth: signup
        invalidMap ('signup', 'post', '/auth/signup', ['', [], {}, {'username': 1}, {'username': 'user@me', 'password': 'foobar', 'email': 'a@a.com'}, {'username:': 'user: me', 'password': 'foobar', 'email': 'a@a.co'}, {'username': 't'}, {'username': '    t    '}, {'username': username}, {'username': username, 'password': 1}, {'username': username, 'password': 'foo'}, {'username': username, 'password': 'foobar'}, {'username': username, 'password': 'foobar', 'email': 'me@something'}, {'username': username, 'password': 'foobar', 'email': 'me@something.com', 'prog_experience': [2]}, {'username': username, 'password': 'foobar', 'email': 'me@something.com', 'prog_experience': 'foo'}, {'username': username, 'password': 'foobar', 'email': 'me@something.com', 'experience_languages': 'python'}]),
        ['valid signup', 'post', '/auth/signup', {}, {'username': username, 'password': 'foobar', 'email': username + '@e2e-testing.com'}, 200, successfulSignup],
        invalidMap ('login', 'post', '/auth/login', ['', [], {}, {'username': 1}, {'username': 'user@me'}, {'username:': 'user: me'}]),
        # Auth: verify & login
        ['valid login, invalid credentials', 'post', '/auth/login', {}, {'username': username, 'password': 'password'}, 403],
        ['verify email (missing fields)', 'get', lambda state: '/auth/verify?' + urllib.parse.urlencode ({'username': 'foobar', 'token': state ['token']}), {}, '', 403],
        ['verify email (invalid username)', 'get', lambda state: '/auth/verify?' + urllib.parse.urlencode ({'username': 'foobar', 'token': state ['token']}), {}, '', 403],
        ['verify email (invalid token)', 'get', lambda state: '/auth/verify?' + urllib.parse.urlencode ({'username': username, 'token': 'foobar'}), {}, '', 403],
        ['verify email', 'get', lambda state: '/auth/verify?' + urllib.parse.urlencode ({'username': username, 'token': state ['token']}), {}, '', 302],
        ['valid login', 'post', '/auth/login', {}, {'username': username, 'password': 'foobar'}, 200, setSentCookies],

        testQuiz('test quiz functions that will succeed', happyFlowTestCasesQuiz),


    ]



if not args.concurrent:
    run_suite(suite)
else:
    counter = 0
    threads = []
    results = []
    errors = []


    def thread_function(counter):
        try:
            ms = run_suite(suite)
            print('Finished concurrent test #' + str(counter))
            results.append(ms)
        except Exception as e:
            print('Concurrent test #' + str(counter), "finished with error")
            errors.append(e)


    print('Starting', args.concurrent, 'concurrent tests')
    while counter < args.concurrent:
        counter += 1
        thread = threading.Thread(target=thread_function, args=[counter])
        thread.start()
        threads.append(thread)

    for thread in threads:
        # join waits until all threads are done
        thread.join()
    print('Done with', args.concurrent, 'concurrent tests,', len(results), 'OK,', len(errors), 'errors,',
          round(sum(results) / (len(results) * 1000), 2), 'seconds average')
