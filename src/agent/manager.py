import os

def ensure_project_setup(project_root: str):
    """
    Ensures that the necessary directories (.ca, playground) exist 
    and .ca is ignored by git.
    """
    ca_dir = os.path.join(project_root, ".ca")
    if not os.path.exists(ca_dir):
        os.makedirs(ca_dir)
        print(f"Created metadata directory: {ca_dir}")

    playground_dir = os.path.join(project_root, "playground")
    if not os.path.exists(playground_dir):
        os.makedirs(playground_dir)
        print(f"Created playground directory: {playground_dir}")

    gitignore_path = os.path.join(project_root, ".gitignore")
    ignore_entries = [".ca/", "playground/"]
    
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            content = f.read()
        
        needed_entries = [e for e in ignore_entries if e not in content]
        
        if needed_entries:
            with open(gitignore_path, "a") as f:
                f.write("\n# Coding Agent storage and playground\n")
                for entry in needed_entries:
                    f.write(f"{entry}\n")
            print(f"Updated .gitignore with: {', '.join(needed_entries)}")
    else:
        with open(gitignore_path, "w") as f:
            f.write("# Coding Agent storage and playground\n")
            for entry in ignore_entries:
                f.write(f"{entry}\n")
        print("Created .gitignore with storage entries.")

if __name__ == "__main__":
    ensure_project_setup(os.getcwd())
