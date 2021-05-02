import argparse
from jenkinsapi.jenkins import Jenkins
import os
import pwd
import sys
import time
import xml.etree.ElementTree as et

server = None


def load_file(filename : str):
	'''Return the contents of the specified file.
	# filename: string, filename to open
	'''
	with open(filename, 'r') as f:
		return f.read()


def get_user_name():
	'''Get the effective user id.'''
	return pwd.getpwuid(os.geteuid()).pw_name

def getKey(user=''):
	'''Get the user's secret Jenkins key from the "jenkins_token.txt" file in the user's home directory.'''
	user = '~' + user
	key_file = 'jenkins_token.txt'
	full_path = os.path.join(os.path.expanduser(user), key_file)
	with open(full_path) as f:
		key = f.readline()
	return key.strip()


def jenkins_connect():
	'''Connect to the Jenkins REST API server.'''
	global server
	try:
		server = Jenkins('http://ubuntu-1:8080', username=get_user_name(), password=getKey())
	except Exception as e:
		raise Exception(f'Connection to Jenkins: { e }')


def build_job(job=None):
	'''Build a Jenkins job.'''
	try:
		if job == None:
			raise Exception('No job name provided')
		if not server.has_job(job):
			raise Exception(f'Job does not exist: { job }')
		server.build_job(job)
		job = server[job]
		qi = job.invoke()
		if qi.is_queued() or qi.is_running():
			print(f'Waiting for { qi } to complete...')
			qi.block_until_complete()
		build = qi.get_build()
		status = build.is_good()
		print(f'BUILD IS COMPLETE: { build }: STATUS: { "good" if build.is_good() else "bad" }')
		return status
	except Exception as e:
		raise Exception(f'build_job(): { e }')


def delete_job(job_name):
	'''Delet a Jenkins job.'''
	try:
		if server[job_name] != None:
			server.delete_job(job_name)
	except:
		raise Exception(f'delete_job(): job does not exist: { job_name }')


def create_job(job_name):
	'''Create job from XML file and how to delete job'''

	if server.has_job(job_name):
		raise Exception(f'create_job(): Job already exists: { job_name }')

	try:
		xml = load_file('emptyjob.xml')

		#print(xml)

		job = server.create_job(jobname=job_name, xml=xml)

		# Get job from Jenkins by job name
		my_job = server[job_name]
		print(f'create_job(): Creating job: { my_job }')

		job_conf = my_job.get_config()

		root = et.fromstring(job_conf.strip())

		builders = root.find('builders')
		shell = et.SubElement(builders, 'hudson.tasks.Shell')
		command = et.SubElement(shell, 'command')
		command.text = '''pwd
ls -l "$(pwd)/.."
echo Done
'''
		new_config = str(et.tostring(root), 'utf8') # Convert to string from bytes
		server[job_name].update_config(new_config)
		print(new_config)
	except Exception as e:
		raise Exception(f'create_job(): { e }')


def exists(job_name):
	'''Check if a job exists. Raises an Exception if it doesn't exist.'''
	if not server.has_job(job_name):
		raise Exception(f'exists(): Job does not exist: { job_name }')


def list_jobs():
	'''List all Jenkins job names, one per line.'''
	for j, _ in server.get_jobs():
		print(j)

def create_arg_parser():
	'''Create and return a command line argument parser.'''
	parser = argparse.ArgumentParser(description='Jenkins CLI to define/build/delete or report on a job')

	parser.add_argument('--job-name', type=str, help='Job name to define, build, delete, or report on.')

	parser.add_argument('--create',
		action='store_true',
		help='Specifies that the job should be created.')

	parser.add_argument('--build',
		action='store_true',
		help='Specifies that the job should be built.')

	parser.add_argument('--delete',
		action='store_true',
		help='Specifies that the job should be deleted instead of created.')

	parser.add_argument('--exists',
		action='store_true',
		help="Return exit code 0 (zero) if the job exists, non-zero if it doesn't.")

	parser.add_argument('--get-config',
		action='store_true',
		help="Print the job configuration.")

	parser.add_argument('--list-jobs',
		action='store_true',
		help="List all Jenkins job names.")

	return parser


def validate_args(args):
	'''Validate the command line arguments.'''
	if not (args.create or args.build or args.delete or args.exists or args.list_jobs or args.get_config):
		print(f'ERROR: Missing arguments\n', file=sys.stderr)
		parser.print_help()
		sys.exit()

	if args.create or args.build or args.delete or args.exists or args.get_config:
		if not args.job_name:
			print(f'ERROR: Missing --job-name option\n')
			parser.print_help()
			sys.exit()


def get_job_config(job_name):
	'''Return the job's XML configuration.'''
	exists(job_name)
	return server[job_name].get_config()


if __name__ == '__main__':

	try:

		parser = create_arg_parser()

		try:
			args = parser.parse_args()
			validate_args(args)
		except SystemExit:
			sys.exit(1)

		jenkins_connect()

		if args.exists:
			exists(args.job_name)
			print(f'Job exists: { args.job_name }', file=sys.stderr)

		if args.create:
			create_job(args.job_name)
			print(f'Job has been created: { args.job_name }', file=sys.stderr)

		if args.build:
			build_job(args.job_name)
			print(f'Job has been built: { args.job_name }', file=sys.stderr)

		if args.delete:
			delete_job(args.job_name)
			print(f'Job has been deleted: { args.job_name }', file=sys.stderr)

		if args.get_config:
			print(get_job_config(args.job_name))

		if args.list_jobs:
			list_jobs()

	except Exception as e:
		print(f'ERROR: { e }', file=sys.stderr)
		sys.exit(3)

