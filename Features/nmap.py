import subprocess
import os

def run_nmap(target, report_file):
    """
    Runs the nmap command with -Pn, verbose mode, and scans for all open ports.
    Saves the output to the specified report file.
    """
    try:
        # Construct the nmap command
        command = ["nmap", "-Pn", "-p-", "-v", target]

        print(f"Running command: {' '.join(command)}\n")

        # Execute the nmap command
        result = subprocess.run(command, text=True, capture_output=True)

        # Check if the command ran successfully
        if result.returncode == 0:
            # Save the output to the report file
            with open(report_file, 'w') as f:
                f.write(result.stdout)
            return "Nmap scan completed successfully."
        else:
            # Save the error output
            with open(report_file, 'w') as f:
                f.write(result.stderr)
            return "Nmap scan encountered an error."
    except FileNotFoundError:
        return "Error: nmap is not installed or not available in the system PATH."
    except Exception as e:
        return f"An unexpected error occurred: {e}"
