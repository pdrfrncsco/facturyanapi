from celery import Task


def dispatch_task(task: Task, *args, **kwargs):
    return task.delay(*args, **kwargs)
