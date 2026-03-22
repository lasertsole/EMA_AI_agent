import time
import streamlit as st
from threading import Thread

from streamlit.delta_generator import DeltaGenerator

class WorkerThread(Thread):
    def __init__(self, container: DeltaGenerator):
        super().__init__()
        self.container = container

    def run(self):
        while True:
            time.sleep(1)
            with self.container:
                print(1)
                st.write("hello world")