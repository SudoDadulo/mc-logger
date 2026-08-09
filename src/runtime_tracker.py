import datetime as dt

class RuntimeTracker:
    def __enter__(self):
        self.start_time = dt.datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = dt.datetime.now()
        runtime = end_time - self.start_time

        print(f"\nProgram runtime statistics:")
        print(f"  Start:   {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  End:     {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Runtime: {runtime.days} days, {runtime.seconds} seconds")

        # Explicitly return false to not catch/supress exceptions
        return False
