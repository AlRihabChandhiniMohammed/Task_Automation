#!/usr/bin/env python3
"""
Task Automation Web App
A web-based interface for scheduling routine tasks like file management and alerts.
"""

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import os
import json
import time
import shutil
import schedule
import threading
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

class TaskManager:
    def __init__(self):
        self.config_file = "web_tasks.json"
        self.tasks = self.load_tasks()
        self.scheduler_thread = None
        self.running = False
        
    def load_tasks(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def save_tasks(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.tasks, f, indent=2)
    
    def add_task(self, name, task_type, schedule_time, **kwargs):
        task = {
            'type': task_type,
            'schedule': schedule_time,
            'created': datetime.now().isoformat(),
            'enabled': True,
            'last_run': None,
            **kwargs
        }
        self.tasks[name] = task
        self.save_tasks()
        self.restart_scheduler()
        return True
    
    def remove_task(self, name):
        if name in self.tasks:
            del self.tasks[name]
            self.save_tasks()
            self.restart_scheduler()
            return True
        return False
    
    def toggle_task(self, name):
        if name in self.tasks:
            self.tasks[name]['enabled'] = not self.tasks[name]['enabled']
            self.save_tasks()
            self.restart_scheduler()
            return True
        return False
    
    def execute_task(self, name, task):
        if not task['enabled']:
            return False
        
        try:
            task_type = task['type']
            result = ""
            
            if task_type == "file_cleanup":
                result = self.execute_file_cleanup(
                    task['source_dir'],
                    task.get('days_old', 7),
                    task.get('file_pattern', '*')
                )
            elif task_type == "file_backup":
                result = self.execute_file_backup(task['source_dir'], task['backup_dir'])
            elif task_type == "alert":
                result = self.execute_alert(task['message'])
            
            self.tasks[name]['last_run'] = datetime.now().isoformat()
            self.tasks[name]['last_result'] = result
            self.save_tasks()
            return True
        except Exception as e:
            self.tasks[name]['last_result'] = f"Error: {str(e)}"
            self.save_tasks()
            return False
    
    def execute_file_cleanup(self, source_dir, days_old=7, file_pattern="*"):
        try:
            source_path = Path(source_dir)
            if not source_path.exists():
                return f"Directory {source_dir} does not exist"
            
            cutoff_time = time.time() - (days_old * 24 * 60 * 60)
            deleted_count = 0
            
            for file_path in source_path.glob(file_pattern):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except Exception:
                        pass
            
            return f"Deleted {deleted_count} files from {source_dir}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def execute_file_backup(self, source_dir, backup_dir):
        try:
            source_path = Path(source_dir)
            backup_path = Path(backup_dir)
            
            if not source_path.exists():
                return f"Source directory {source_dir} does not exist"
            
            backup_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_subdir = backup_path / f"backup_{timestamp}"
            
            shutil.copytree(source_dir, backup_subdir)
            return f"Backup completed: {source_dir} -> {backup_subdir}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def execute_alert(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_msg = f"[{timestamp}] ALERT: {message}"
        
        # Log to file
        with open("web_alerts.log", "a") as f:
            f.write(alert_msg + "\n")
        
        return f"Alert logged: {message}"
    
    def schedule_tasks(self):
        schedule.clear()
        
        for name, task in self.tasks.items():
            if not task['enabled']:
                continue
            
            schedule_time = task['schedule']
            job = lambda t=task, n=name: self.execute_task(n, t)
            
            if schedule_time.startswith("every"):
                parts = schedule_time.split()
                if len(parts) >= 2:
                    interval = parts[1]
                    if interval.endswith("m"):
                        schedule.every(int(interval.rstrip("m"))).minutes.do(job)
                    elif interval.endswith("h"):
                        schedule.every(int(interval.rstrip("h"))).hours.do(job)
                    elif interval == "day":
                        schedule.every().day.do(job)
            elif ":" in schedule_time:
                schedule.every().day.at(schedule_time).do(job)
    
    def run_scheduler(self):
        self.schedule_tasks()
        self.running = True
        
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def start_scheduler(self):
        if not self.running:
            self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
            self.scheduler_thread.start()
    
    def stop_scheduler(self):
        self.running = False
    
    def restart_scheduler(self):
        self.stop_scheduler()
        time.sleep(1)
        self.start_scheduler()

# Global task manager instance
task_manager = TaskManager()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Automation Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            padding: 30px; 
            text-align: center; 
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; font-size: 1.1em; }
        .content { padding: 30px; }
        .section { margin-bottom: 40px; }
        .section h2 { 
            color: #333; 
            margin-bottom: 20px; 
            font-size: 1.8em;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        .form-group { 
            margin-bottom: 20px; 
        }
        .form-group label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: 600;
            color: #555;
        }
        .form-group input, .form-group select, .form-group textarea { 
            width: 100%; 
            padding: 12px; 
            border: 2px solid #e1e5e9;
            border-radius: 8px; 
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .form-row { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 20px; 
        }
        .btn { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; 
            padding: 12px 25px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .btn-danger { 
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
        }
        .btn-danger:hover {
            box-shadow: 0 5px 15px rgba(255, 107, 107, 0.4);
        }
        .btn-success { 
            background: linear-gradient(135deg, #2ed573 0%, #1e90ff 100%);
        }
        .btn-success:hover {
            box-shadow: 0 5px 15px rgba(46, 213, 115, 0.4);
        }
        .task-card { 
            background: #f8f9ff;
            border: 2px solid #e1e5e9;
            border-radius: 12px; 
            padding: 20px; 
            margin-bottom: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .task-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .task-header { 
            display: flex; 
            justify-content: between; 
            align-items: center; 
            margin-bottom: 15px; 
        }
        .task-name { 
            font-size: 1.3em; 
            font-weight: 600; 
            color: #333;
        }
        .task-status { 
            padding: 5px 12px; 
            border-radius: 20px; 
            font-size: 0.9em; 
            font-weight: 600;
        }
        .status-enabled { 
            background: #d4edda; 
            color: #155724; 
        }
        .status-disabled { 
            background: #f8d7da; 
            color: #721c24; 
        }
        .task-details { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 10px; 
            margin-bottom: 15px; 
        }
        .task-detail { 
            font-size: 0.9em; 
            color: #666; 
        }
        .task-detail strong { 
            color: #333; 
        }
        .task-actions { 
            display: flex; 
            gap: 10px; 
            flex-wrap: wrap; 
        }
        .status-bar {
            background: #f8f9ff;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            text-align: center;
        }
        .scheduler-status {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            margin: 0 10px;
        }
        .scheduler-running {
            background: #d4edda;
            color: #155724;
        }
        .scheduler-stopped {
            background: #f8d7da;
            color: #721c24;
        }
        @media (max-width: 768px) {
            .form-row { grid-template-columns: 1fr; }
            .task-actions { justify-content: center; }
            .header h1 { font-size: 2em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Task Automation Dashboard</h1>
            <p>Schedule and manage your routine tasks with ease</p>
        </div>
        
        <div class="content">
            <div class="status-bar">
                <span class="scheduler-status {{ 'scheduler-running' if scheduler_running else 'scheduler-stopped' }}">
                    {{ '🟢 Scheduler Running' if scheduler_running else '🔴 Scheduler Stopped' }}
                </span>
                <button class="btn {{ 'btn-danger' if scheduler_running else 'btn-success' }}" 
                        onclick="toggleScheduler()">
                    {{ 'Stop Scheduler' if scheduler_running else 'Start Scheduler' }}
                </button>
            </div>

            <div class="section">
                <h2>➕ Add New Task</h2>
                <form method="POST" action="/add_task">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="name">Task Name:</label>
                            <input type="text" id="name" name="name" required>
                        </div>
                        <div class="form-group">
                            <label for="type">Task Type:</label>
                            <select id="type" name="type" required onchange="updateFields()">
                                <option value="">Select Type</option>
                                <option value="file_cleanup">File Cleanup</option>
                                <option value="file_backup">File Backup</option>
                                <option value="alert">Alert/Reminder</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="schedule">Schedule:</label>
                        <select id="schedule" name="schedule" required>
                            <option value="every 30m">Every 30 minutes</option>
                            <option value="every 1h">Every hour</option>
                            <option value="every 2h">Every 2 hours</option>
                            <option value="every day">Every day</option>
                            <option value="09:00">Daily at 9:00 AM</option>
                            <option value="18:00">Daily at 6:00 PM</option>
                        </select>
                    </div>
                    
                    <div id="file-fields" style="display: none;">
                        <div class="form-group">
                            <label for="source_dir">Source Directory:</label>
                            <input type="text" id="source_dir" name="source_dir" placeholder="/path/to/source">
                        </div>
                        <div id="backup-field" class="form-group" style="display: none;">
                            <label for="backup_dir">Backup Directory:</label>
                            <input type="text" id="backup_dir" name="backup_dir" placeholder="/path/to/backup">
                        </div>
                        <div id="cleanup-fields" style="display: none;">
                            <div class="form-row">
                                <div class="form-group">
                                    <label for="days_old">Days Old:</label>
                                    <input type="number" id="days_old" name="days_old" value="7" min="1">
                                </div>
                                <div class="form-group">
                                    <label for="file_pattern">File Pattern:</label>
                                    <input type="text" id="file_pattern" name="file_pattern" value="*" placeholder="*.tmp">
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div id="alert-field" class="form-group" style="display: none;">
                        <label for="message">Alert Message:</label>
                        <textarea id="message" name="message" rows="3" placeholder="Enter your alert message"></textarea>
                    </div>
                    
                    <button type="submit" class="btn">Add Task</button>
                </form>
            </div>

            <div class="section">
                <h2>📋 Active Tasks ({{ tasks|length }})</h2>
                {% if tasks %}
                    {% for name, task in tasks.items() %}
                    <div class="task-card">
                        <div class="task-header">
                            <div class="task-name">{{ name }}</div>
                            <div class="task-status {{ 'status-enabled' if task.enabled else 'status-disabled' }}">
                                {{ 'Enabled' if task.enabled else 'Disabled' }}
                            </div>
                        </div>
                        
                        <div class="task-details">
                            <div class="task-detail">
                                <strong>Type:</strong> {{ task.type|title }}
                            </div>
                            <div class="task-detail">
                                <strong>Schedule:</strong> {{ task.schedule }}
                            </div>
                            <div class="task-detail">
                                <strong>Created:</strong> {{ task.created[:16] }}
                            </div>
                            {% if task.last_run %}
                            <div class="task-detail">
                                <strong>Last Run:</strong> {{ task.last_run[:16] }}
                            </div>
                            {% endif %}
                        </div>
                        
                        {% if task.last_result %}
                        <div class="task-detail" style="margin-bottom: 15px;">
                            <strong>Last Result:</strong> {{ task.last_result }}
                        </div>
                        {% endif %}
                        
                        <div class="task-actions">
                            <button class="btn" onclick="executeTask('{{ name }}')">
                                Run Now
                            </button>
                            <button class="btn {{ 'btn-danger' if task.enabled else 'btn-success' }}" 
                                    onclick="toggleTask('{{ name }}')">
                                {{ 'Disable' if task.enabled else 'Enable' }}
                            </button>
                            <button class="btn btn-danger" onclick="removeTask('{{ name }}')">
                                Delete
                            </button>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="task-card">
                        <p style="text-align: center; color: #666; font-size: 1.1em;">
                            No tasks configured yet. Add your first task above! 🎯
                        </p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>

    <script>
        function updateFields() {
            const type = document.getElementById('type').value;
            const fileFields = document.getElementById('file-fields');
            const backupField = document.getElementById('backup-field');
            const cleanupFields = document.getElementById('cleanup-fields');
            const alertField = document.getElementById('alert-field');
            
            // Hide all fields first
            fileFields.style.display = 'none';
            backupField.style.display = 'none';
            cleanupFields.style.display = 'none';
            alertField.style.display = 'none';
            
            if (type === 'file_cleanup') {
                fileFields.style.display = 'block';
                cleanupFields.style.display = 'block';
            } else if (type === 'file_backup') {
                fileFields.style.display = 'block';
                backupField.style.display = 'block';
            } else if (type === 'alert') {
                alertField.style.display = 'block';
            }
        }
        
        async function executeTask(name) {
            const response = await fetch(`/execute/${name}`, { method: 'POST' });
            if (response.ok) {
                location.reload();
            }
        }
        
        async function toggleTask(name) {
            const response = await fetch(`/toggle/${name}`, { method: 'POST' });
            if (response.ok) {
                location.reload();
            }
        }
        
        async function removeTask(name) {
            if (confirm(`Are you sure you want to delete the task "${name}"?`)) {
                const response = await fetch(`/remove/${name}`, { method: 'POST' });
                if (response.ok) {
                    location.reload();
                }
            }
        }
        
        async function toggleScheduler() {
            const response = await fetch('/toggle_scheduler', { method: 'POST' });
            if (response.ok) {
                location.reload();
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, 
                                tasks=task_manager.tasks, 
                                scheduler_running=task_manager.running)

@app.route('/add_task', methods=['POST'])
def add_task():
    name = request.form['name']
    task_type = request.form['type']
    schedule_time = request.form['schedule']
    
    kwargs = {}
    if task_type in ['file_cleanup', 'file_backup']:
        kwargs['source_dir'] = request.form['source_dir']
    if task_type == 'file_backup':
        kwargs['backup_dir'] = request.form['backup_dir']
    if task_type == 'file_cleanup':
        kwargs['days_old'] = int(request.form.get('days_old', 7))
        kwargs['file_pattern'] = request.form.get('file_pattern', '*')
    if task_type == 'alert':
        kwargs['message'] = request.form['message']
    
    task_manager.add_task(name, task_type, schedule_time, **kwargs)
    return redirect(url_for('index'))

@app.route('/execute/<name>', methods=['POST'])
def execute_task(name):
    if name in task_manager.tasks:
        task_manager.execute_task(name, task_manager.tasks[name])
    return jsonify({'status': 'success'})

@app.route('/toggle/<name>', methods=['POST'])
def toggle_task(name):
    task_manager.toggle_task(name)
    return jsonify({'status': 'success'})

@app.route('/remove/<name>', methods=['POST'])
def remove_task(name):
    task_manager.remove_task(name)
    return jsonify({'status': 'success'})

@app.route('/toggle_scheduler', methods=['POST'])
def toggle_scheduler():
    if task_manager.running:
        task_manager.stop_scheduler()
    else:
        task_manager.start_scheduler()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    # Start the scheduler by default
    task_manager.start_scheduler()
    
    print("🚀 Task Automation Web App Starting...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop the server")
    
    app.run(debug=True, host='0.0.0.0', port=5000)