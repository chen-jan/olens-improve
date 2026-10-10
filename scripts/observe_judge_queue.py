"""Compatibility CLI for the bounded, autocommit operational observer.

The former implementation held BEGIN across every epoch/event lookup. Use the
current observer instead so completed queries release their read locks promptly.
Historical checkpoint artifacts remain unchanged.
"""
from observe_judge_queue_window import main


if __name__ == '__main__':
    main()
