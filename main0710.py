import serial
import serial.tools.list_ports
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, StringVar, filedialog, scrolledtext
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from piper_sdk import *
import os

# 定义机械臂目标位置
TARGET_ENDPOSE0 = [55, 0, 205, 0, 85, 0]  # Home position
TARGET_ENDPOSE1 = [173.258, 0, 298.551, 180, 20, 180]  # Ready point 1
TARGET_ENDPOSE2 = [225.607, 0, 232.239, 180, 11.177, 180]  # Ready point 2
TARGET_ENDPOSE3 = [359.182, 245.769, 234.506, 180, 21.492, -145.66]  # Small tomato position (30-50mm)
TARGET_ENDPOSE4 = [339.458, 0, 255.015, 180, 14.873, -180]  # Medium tomato position (50-60mm)
TARGET_ENDPOSE5 = [369.766, -229.657, 233.916, 180, 21.381, 147.951]  # Large tomato position (60-70mm)

class TomatoClassifierApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Tomato Classification System")
        self.root.geometry("900x700")
        self.root.configure(bg="#f0f8ff")
        
        # 设置番茄主题颜色
        self.style = ttk.Style()
        self.style.configure("Tomato.TFrame", background="#ffefef")
        self.style.configure("Tomato.TLabelframe", background="#fff0f5", font=("Arial", 10, "bold"))
        self.style.configure("Tomato.TLabelframe.Label", background="#fff0f5", foreground="#b22222")
        self.style.configure("Tomato.TButton", background="#ff6b6b", foreground="white", font=("Arial", 10, "bold"))
        self.style.configure("Tomato.TLabel", background="#fff0f5", font=("Arial", 9))
        self.style.configure("Header.TLabel", background="#ffc4c4", foreground="#8b0000", 
                            font=("Arial", 11, "bold"), padding=5)
        
        # 串口相关变量
        self.serial_port = None
        self.baudrate = 115200
        
        # 机器学习模型相关变量
        self.models = None
        self.scaler = None
        self.features = None
        self.training_in_progress = False
        self.training_completed = False
        self.training_file_path = ""
        self.prediction_file_path = ""
        
        # 电阻输入变量
        self.resistance_vars = [StringVar(), StringVar(), StringVar()]
        
        # 创建界面
        self.create_widgets()
        
        # 自动刷新串口列表
        self.refresh_ports()
        
        # 设置默认文件路径
        self.default_data_dir = os.path.join(os.path.expanduser("~"), "6-281")
        if not os.path.exists(self.default_data_dir):
            os.makedirs(self.default_data_dir)
            
        self.training_file_var.set(os.path.join(self.default_data_dir, "data1.csv"))
        self.prediction_file_var.set(os.path.join(self.default_data_dir, "data3.csv"))
        
        # 添加标题
        title_label = ttk.Label(self.root, text="Guangxi University", 
                              font=("Arial", 16, "bold"), foreground="#8b0000", 
                              background="#ffefd5", anchor="center")
        title_label.pack(fill=tk.X, padx=10, pady=10)

    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧面板 - 串口控制
        left_panel = ttk.LabelFrame(main_frame, text="Serial Port Control", padding=10, style="Tomato.TLabelframe")
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # 串口设置区域
        port_frame = ttk.LabelFrame(left_panel, text="Serial Settings", padding=10, style="Tomato.TLabelframe")
        port_frame.pack(fill=tk.X, pady=5)
        
        # 串口选择
        ttk.Label(port_frame, text="Select Port:", style="Tomato.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.port_combobox = ttk.Combobox(port_frame, width=20)
        self.port_combobox.grid(row=0, column=1, padx=5, pady=5)
        
        # 刷新按钮
        self.refresh_button = ttk.Button(port_frame, text="Refresh", width=8, 
                                        command=self.refresh_ports, style="Tomato.TButton")
        self.refresh_button.grid(row=0, column=2, padx=5, pady=5)
        
        # 波特率选择
        ttk.Label(port_frame, text="Baud Rate:", style="Tomato.TLabel").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.baudrate_combobox = ttk.Combobox(port_frame, width=10)
        self.baudrate_combobox['values'] = (9600, 19200, 38400, 57600, 115200)
        self.baudrate_combobox.set(115200)
        self.baudrate_combobox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # 连接/断开按钮
        self.connect_button = ttk.Button(port_frame, text="Open Port", width=8, 
                                        command=self.toggle_connection, style="Tomato.TButton")
        self.connect_button.grid(row=1, column=2, padx=5, pady=5)
        
        # 爪控制区域
        claw_frame = ttk.LabelFrame(left_panel, text="Claw Control", padding=10, style="Tomato.TLabelframe")
        claw_frame.pack(fill=tk.X, pady=5)
        
        self.open_claw_button = ttk.Button(
            claw_frame, 
            text="Open Claw", 
            width=15,
            command=lambda: self.send_claw_command("open"),
            state=tk.DISABLED,
            style="Tomato.TButton"
        )
        self.open_claw_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.close_claw_button = ttk.Button(
            claw_frame, 
            text="Close Claw", 
            width=15,
            command=lambda: self.send_claw_command("close"),
            state=tk.DISABLED,
            style="Tomato.TButton"
        )
        self.close_claw_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 右侧面板 - 模型预测
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 模型预测部分
        model_frame = ttk.LabelFrame(right_panel, text="Model Prediction", padding=10, style="Tomato.TLabelframe")
        model_frame.pack(fill=tk.X, pady=5)
        
        # 数据加载方式选择
        self.data_source = tk.IntVar()
        self.data_source.set(1)  # 默认选择文件加载方式
        
        file_radio = ttk.Radiobutton(
            model_frame, 
            text="Load from CSV file", 
            variable=self.data_source, 
            value=1,
            style="Tomato.TLabel"
        )
        file_radio.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        
        manual_radio = ttk.Radiobutton(
            model_frame, 
            text="Manual Input", 
            variable=self.data_source, 
            value=2,
            style="Tomato.TLabel"
        )
        manual_radio.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # 分隔线
        ttk.Separator(model_frame, orient=tk.HORIZONTAL).grid(row=1, column=0, columnspan=3, sticky="ew", pady=10)
        
        # 文件加载面板
        self.file_panel = ttk.Frame(model_frame)
        self.file_panel.grid(row=2, column=0, columnspan=3, sticky="ew")
        
        ttk.Label(self.file_panel, text="Prediction File:", style="Tomato.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.prediction_file_var = StringVar()
        predict_file_entry = ttk.Entry(self.file_panel, textvariable=self.prediction_file_var, width=40)
        predict_file_entry.grid(row=0, column=1, padx=5, pady=5)
        
        browse_predict_btn = ttk.Button(self.file_panel, text="Browse...", width=8, 
                                       command=self.browse_prediction_file, style="Tomato.TButton")
        browse_predict_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # 手动输入面板
        self.manual_panel = ttk.Frame(model_frame)
        self.manual_panel.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.manual_panel.grid_remove()  # 初始隐藏
        
        # 添加电阻值输入标签
        ttk.Label(self.manual_panel, text="Resistance Input:", style="Tomato.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        
        # 创建三个输入框
        for i in range(3):
            ttk.Label(self.manual_panel, text=f"Sensor {i+1} (Ω):", style="Tomato.TLabel").grid(row=i+1, column=0, padx=5, pady=5, sticky=tk.W)
            entry = ttk.Entry(self.manual_panel, textvariable=self.resistance_vars[i], width=15)
            entry.grid(row=i+1, column=1, padx=5, pady=5)
        
        # 绑定数据源选择变化事件
        self.data_source.trace_add("write", self.toggle_data_input)
        
        # 训练模型面板
        training_frame = ttk.Frame(model_frame)
        training_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        
        ttk.Label(training_frame, text="Training File:", style="Tomato.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.training_file_var = StringVar()
        training_file_entry = ttk.Entry(training_frame, textvariable=self.training_file_var, width=40)
        training_file_entry.grid(row=0, column=1, padx=5, pady=5)
        
        browse_train_btn = ttk.Button(training_frame, text="Browse...", width=8, 
                                     command=self.browse_training_file, style="Tomato.TButton")
        browse_train_btn.grid(row=0, column=2, padx=5, pady=5)
        
        self.train_button = ttk.Button(
            training_frame, 
            text="Train Model", 
            command=self.train_model,
            state=tk.NORMAL,
            style="Tomato.TButton"
        )
        self.train_button.grid(row=1, column=1, pady=10)
        
        # 预测按钮
        self.predict_button = ttk.Button(
            model_frame, 
            text="Predict", 
            command=self.predict_data,
            state=tk.DISABLED,
            style="Tomato.TButton"
        )
        self.predict_button.grid(row=5, column=0, columnspan=3, pady=10)
        
        # 预测结果显示区域
        result_frame = ttk.LabelFrame(model_frame, text="Prediction Results", padding=10, style="Tomato.TLabelframe")
        result_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=5)
        
        self.result_text = scrolledtext.ScrolledText(result_frame, height=10, width=70)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.result_text.config(state=tk.DISABLED, bg="#fffafa", font=("Arial", 9))
        
        # 机械臂控制部分
        arm_frame = ttk.LabelFrame(right_panel, text="Robot Arm Control", padding=10, style="Tomato.TLabelframe")
        arm_frame.pack(fill=tk.X, pady=5)
        
        # 分类控制
        classify_frame = ttk.Frame(arm_frame)
        classify_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(classify_frame, text="Classification:", style="Tomato.TLabel").pack(side=tk.LEFT, padx=5)
        
        self.classify_button = ttk.Button(
            classify_frame, 
            text="Classify", 
            command=self.predict_and_classify,
            state=tk.NORMAL,
            style="Tomato.TButton"
        )
        self.classify_button.pack(side=tk.LEFT, padx=5)
        
        self.execute_button = ttk.Button(
            classify_frame, 
            text="Execute", 
            command=self.execute_classification,
            state=tk.DISABLED,
            style="Tomato.TButton"
        )
        self.execute_button.pack(side=tk.LEFT, padx=5)
        
        # 机械臂位置控制
        home_frame = ttk.Frame(arm_frame)
        home_frame.pack(fill=tk.X, pady=5)
        
        # 添加移动到准备点1按钮
        self.ready1_button = ttk.Button(
            home_frame, 
            text="Move to Ready Point 1", 
            command=lambda: self.move_arm(TARGET_ENDPOSE1),
            state=tk.NORMAL,
            style="Tomato.TButton"
        )
        self.ready1_button.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        
        # 添加移动到准备点2按钮
        self.ready2_button = ttk.Button(
            home_frame, 
            text="Move to Ready Point 2", 
            command=lambda: self.move_arm(TARGET_ENDPOSE2),
            state=tk.NORMAL,
            style="Tomato.TButton"
        )
        self.ready2_button.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        
        # 移动到原点按钮
        self.home_button = ttk.Button(
            home_frame, 
            text="Move to Home", 
            command=lambda: self.move_arm(TARGET_ENDPOSE0),
            state=tk.NORMAL,
            style="Tomato.TButton"
        )
        self.home_button.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("System Ready")
        status_bar = ttk.Label(
            self.root, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN, 
            anchor=tk.W,
            background="#ffc4c4",
            foreground="#8b0000",
            font=("Arial", 9)
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        # 将状态栏中的"番茄分类采摘系统"改为"Guangxi University"
        status_bar.config(text="Guangxi University", anchor=tk.CENTER)

    def toggle_data_input(self, *args):
        """切换数据输入方式"""
        if self.data_source.get() == 1:  # 文件加载
            self.file_panel.grid()
            self.manual_panel.grid_remove()
        else:  # 手动输入
            self.file_panel.grid_remove()
            self.manual_panel.grid()

    def refresh_ports(self):
        """刷新可用的串口列表"""
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_combobox['values'] = port_list
        if port_list:
            self.port_combobox.current(0)
            self.status_var.set("Serial ports detected")
        else:
            self.port_combobox.set('')
            self.status_var.set("No serial ports found")

    def toggle_connection(self):
        """打开或关闭串口连接"""
        if self.serial_port and self.serial_port.is_open:
            self.close_connection()
            self.connect_button.config(text="Open Port")
            self.open_claw_button.config(state=tk.DISABLED)
            self.close_claw_button.config(state=tk.DISABLED)
            self.status_var.set("Serial port disconnected")
        else:
            self.open_connection()
            if self.serial_port and self.serial_port.is_open:
                self.connect_button.config(text="Close Port")
                self.open_claw_button.config(state=tk.NORMAL)
                self.close_claw_button.config(state=tk.NORMAL)
                self.status_var.set(f"Connected to {self.serial_port.port}, {self.baudrate} baud")

    def open_connection(self):
        """打开串口连接"""
        port = self.port_combobox.get()
        if not port:
            messagebox.showerror("Error", "Please select a serial port")
            return
            
        try:
            baud = int(self.baudrate_combobox.get())
            self.baudrate = baud
        except ValueError:
            messagebox.showerror("Error", "Invalid baud rate")
            return
            
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to open serial port:\n{str(e)}")
            self.status_var.set(f"Connection failed: {str(e)}")

    def close_connection(self):
        """关闭串口连接"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

    def send_claw_command(self, action):
        """发送爪控制命令"""
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showwarning("Warning", "Serial port not connected")
            return
            
        try:
            if action == "open":
                # 打开爪 HEX: 7b 01 02 00 20 49 20 00 c8 F9 7d
                command = bytes.fromhex("7b01020020492000c8f97d")
                self.status_var.set("Sending: Open claw command")
            else:
                # 关闭爪 HEX: 7b 01 02 01 20 49 20 00 c8 F8 7d
                command = bytes.fromhex("7b01020120492000c8f87d")
                self.status_var.set("Sending: Close claw command")
                
            self.serial_port.write(command)
            
        except Exception as e:
            messagebox.showerror("Send Error", str(e))
            self.status_var.set(f"Send failed: {str(e)}")
    
    def browse_training_file(self):
        """浏览选择训练数据文件"""
        file_path = filedialog.askopenfilename(
            title="Select Training Data File",
            initialdir=self.default_data_dir,
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )
        if file_path:
            self.training_file_var.set(file_path)
    
    def browse_prediction_file(self):
        """浏览选择预测数据文件"""
        file_path = filedialog.askopenfilename(
            title="Select Prediction Data File",
            initialdir=self.default_data_dir,
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )
        if file_path:
            self.prediction_file_var.set(file_path)
    
    def train_model(self):
        """训练机器学习模型"""
        if self.training_in_progress:
            return
            
        training_file = self.training_file_var.get()
        if not training_file:
            messagebox.showerror("Error", "Please select a training data file")
            return
            
        if not os.path.exists(training_file):
            messagebox.showerror("Error", f"Training file not found: {training_file}")
            return
            
        # 在后台线程中执行训练
        self.training_in_progress = True
        self.train_button.config(state=tk.DISABLED, text="Training...")
        self.status_var.set("Starting model training...")
        
        threading.Thread(target=self._train_model_thread, args=(training_file,), daemon=True).start()
    
    def _train_model_thread(self, training_file):
        """在后台线程中训练模型"""
        try:
            # 加载数据
            data = self.load_data(training_file)

            # 预处理
            X, y_diameter, y_height, y_weight, scaler, features = self.preprocess_data(data)
            
            # 保存特征列表和标准化器
            self.features = features
            self.scaler = scaler

            # 划分训练测试集
            X_train, X_test, y_dia_train, y_dia_test, y_ht_train, y_ht_test, y_wt_train, y_wt_test = train_test_split(
                X, y_diameter, y_height, y_weight, test_size=0.2, random_state=42
            )

            # 训练模型
            self.models = self.train_models(X_train, y_dia_train, y_ht_train, y_wt_train)
            
            # 更新UI
            self.training_completed = True
            self.root.after(0, self.update_training_status, "Training completed!", True)
            
        except Exception as e:
            self.root.after(0, self.update_training_status, f"Training failed: {str(e)}", False)
    
    def update_training_status(self, message, success):
        """更新训练状态"""
        self.training_in_progress = False
        self.train_button.config(state=tk.NORMAL, text="Train Model")
        self.status_var.set(message)
        
        if success:
            # 启用预测按钮
            self.predict_button.config(state=tk.NORMAL)
            
            # 更新结果文本框
            self.result_text.config(state=tk.NORMAL)
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, "Model training completed!\n\n")
            self.result_text.insert(tk.END, "Training data statistics:\n")
            self.result_text.insert(tk.END, f"- Training samples: {len(self.scaler.mean_)}\n")
            self.result_text.insert(tk.END, f"- Features: {len(self.features)}\n")
            self.result_text.config(state=tk.DISABLED)
            
    def predict_data(self):
        """执行预测"""
        if not self.models or not self.scaler or not self.features:
            messagebox.showerror("Error", "Please train the model first")
            return
        
        # 根据选择的数据源执行预测
        if self.data_source.get() == 1:  # 文件预测
            prediction_file = self.prediction_file_var.get()
            if not prediction_file:
                messagebox.showerror("Error", "Please select a prediction data file")
                return
                
            if not os.path.exists(prediction_file):
                messagebox.showerror("Error", f"Prediction file not found: {prediction_file}")
                return
                
            # 在后台线程中执行预测
            self.status_var.set("Starting prediction...")
            threading.Thread(target=self._predict_from_file_thread, args=(prediction_file,), daemon=True).start()
        
        else:  # 手动输入预测
            try:
                # 获取电阻值
                resistances = []
                for i, var in enumerate(self.resistance_vars):
                    try:
                        value = float(var.get())
                        resistances.append(value)
                    except ValueError:
                        messagebox.showerror("Input Error", f"Invalid resistance value for Sensor {i+1}")
                        return
                
                # 创建临时DataFrame
                predict_data = pd.DataFrame([resistances], 
                                           columns=['sensor1_resistance', 'sensor2_resistance', 'sensor3_resistance'])
                
                # 生成衍生特征
                predict_data['resistance_avg'] = predict_data.mean(axis=1)
                predict_data['resistance_std'] = predict_data.std(axis=1)
                
                # 创建特征矩阵
                X_predict = predict_data[self.features]
                
                # 标准化特征
                X_predict_scaled = self.scaler.transform(X_predict)
                X_predict_scaled_df = pd.DataFrame(X_predict_scaled, columns=self.features)
                
                # 进行预测
                rf_dia, rf_ht, rf_wt = self.models
                dia_pred = rf_dia.predict(X_predict_scaled_df)
                ht_pred = rf_ht.predict(X_predict_scaled_df)
                wt_pred = rf_wt.predict(X_predict_scaled_df)
                
                # 显示预测结果
                self.show_prediction_results(dia_pred, ht_pred, wt_pred, "Manual Input")
                
            except Exception as e:
                messagebox.showerror("Prediction Error", str(e))
                self.status_var.set(f"Prediction failed: {str(e)}")
    
    def _predict_from_file_thread(self, prediction_file):
        """在后台线程中执行文件预测"""
        try:
            # 调用预测函数
            dia_pred, ht_pred, wt_pred = self.predict_from_csv(
                self.models, 
                self.scaler, 
                self.features, 
                prediction_file
            )
            
            # 更新结果文本框
            self.root.after(0, self.show_prediction_results, dia_pred, ht_pred, wt_pred, prediction_file)
            
        except Exception as e:
            self.root.after(0, self.update_prediction_status, f"Prediction failed: {str(e)}")
    
    def show_prediction_results(self, dia_pred, ht_pred, wt_pred, source):
        """显示预测结果"""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        
        self.result_text.insert(tk.END, f"Prediction Results ({source}):\n\n")
        self.result_text.insert(tk.END, "Sample | Diameter(mm) | Height(mm) | Weight(g) | Classification\n")
        self.result_text.insert(tk.END, "-" * 60 + "\n")
        
        for i in range(len(dia_pred)):
            # 根据直径进行分类判断
            if 30 <= dia_pred[i] < 50:
                classification = "Small Tomato"
            elif 50 <= dia_pred[i] < 60:
                classification = "Medium Tomato"
            elif 60 <= dia_pred[i] <= 70:
                classification = "Large Tomato"
            else:
                classification = "Unknown"
                
            self.result_text.insert(tk.END, f"{i+1:>6} | {dia_pred[i]:>9.2f} | {ht_pred[i]:>8.2f} | {wt_pred[i]:>8.2f} | {classification}\n")
        
        # 保存第一个样本的预测直径用于分类
        if len(dia_pred) > 0:
            self.first_diameter = dia_pred[0]
            self.result_text.insert(tk.END, "\n")
            self.result_text.insert(tk.END, f"First sample predicted diameter: {self.first_diameter:.2f} mm\n")
            
            # 显示分类结果
            if 30 <= self.first_diameter < 50:
                self.result_text.insert(tk.END, "Classification: Small Tomato\n")
            elif 50 <= self.first_diameter < 60:
                self.result_text.insert(tk.END, "Classification: Medium Tomato\n")
            elif 60 <= self.first_diameter <= 70:
                self.result_text.insert(tk.END, "Classification: Large Tomato\n")
            else:
                self.result_text.insert(tk.END, "Classification: Unknown\n")
            
            # 启用执行分类按钮
            self.execute_button.config(state=tk.NORMAL)
        
        self.result_text.config(state=tk.DISABLED)
        self.status_var.set("Prediction completed!")
    
    def predict_and_classify(self):
        """执行预测并进行分类判断"""
        self.predict_data()
    
    def execute_classification(self):
        """执行分类操作"""
        if hasattr(self, 'first_diameter'):
            if 30 <= self.first_diameter < 50:
                self.status_var.set("Diameter 30-50mm (Small Tomato), moving to position 3")
                self.move_arm(TARGET_ENDPOSE3)
            elif 50 <= self.first_diameter < 60:
                self.status_var.set("Diameter 50-60mm (Medium Tomato), moving to position 4")
                self.move_arm(TARGET_ENDPOSE4)
            elif 60 <= self.first_diameter <= 70:
                self.status_var.set("Diameter 60-70mm (Large Tomato), moving to position 5")
                self.move_arm(TARGET_ENDPOSE5)
            else:
                messagebox.showwarning("Warning", "Tomato diameter is not in valid range (30-70mm)")
                self.status_var.set("Tomato diameter out of range")
        else:
            messagebox.showwarning("Warning", "Please run prediction first")
            
    def move_arm(self, coords):
        """移动机械臂到指定位置"""
        try:
            self.status_var.set(f"Moving robot arm to position: {coords}")
            endpose(coords)
            self.status_var.set(f"Robot arm moved to target position")
        except Exception as e:
            messagebox.showerror("Robot Arm Error", f"Failed to move robot arm: {str(e)}")
            self.status_var.set(f"Robot arm movement failed: {str(e)}")
    
    def update_prediction_status(self, message):
        """更新预测状态"""
        self.status_var.set(message)
    
    # 以下是机器学习相关函数
    def load_data(self, file_path):
        """加载并打乱实验数据"""
        try:
            data = pd.read_csv(file_path)
            return data.sample(frac=1, random_state=42).reset_index(drop=True)
        except FileNotFoundError:
            raise Exception(f"File not found: {file_path}")
        except Exception as e:
            raise Exception(f"Error loading data: {str(e)}")

    def preprocess_data(self, data):
        """数据预处理与特征工程"""
        # 删除含有缺失值的行
        data = data.dropna()

        # 生成衍生特征
        data['resistance_avg'] = data[['sensor1_resistance', 'sensor2_resistance', 'sensor3_resistance']].mean(axis=1)
        data['resistance_std'] = data[['sensor1_resistance', 'sensor2_resistance', 'sensor3_resistance']].std(axis=1)

        # 分离特征和目标
        features = ['sensor1_resistance', 'sensor2_resistance', 'sensor3_resistance',
                    'resistance_avg', 'resistance_std']
        X = data[features]
        y_diameter = data['diameter']
        y_height = data['height']
        y_weight = data['weight']

        # 数据标准化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=features)

        return X_scaled, y_diameter, y_height, y_weight, scaler, features

    def train_models(self, X_train, y_dia_train, y_ht_train, y_wt_train):
        """训练优化后的随机森林模型"""
        # 直径预测模型
        rf_dia = RandomForestRegressor(
            n_estimators=500,
            max_depth=10,
            min_samples_leaf=5,
            max_features=0.8,
            random_state=42
        )
        rf_dia.fit(X_train, y_dia_train)

        # 高度预测模型
        rf_ht = RandomForestRegressor(
            n_estimators=500,
            max_depth=10,
            min_samples_leaf=5,
            max_features=0.8,
            random_state=42
        )
        rf_ht.fit(X_train, y_ht_train)

        # 重量预测模型
        rf_wt = RandomForestRegressor(
            n_estimators=500,
            max_depth=10,
            min_samples_leaf=5,
            max_features=0.8,
            random_state=42
        )
        rf_wt.fit(X_train, y_wt_train)

        return (rf_dia, rf_ht, rf_wt)

    def predict_from_csv(self, models, scaler, features, csv_path):
        """从CSV文件读取数据并预测尺寸"""
        rf_dia, rf_ht, rf_wt = models
        
        try:
            # 加载预测数据
            predict_data = pd.read_csv(csv_path)
            
            # 检查数据是否包含所需的列
            required_cols = ['sensor1_resistance', 'sensor2_resistance', 'sensor3_resistance']
            if not all(col in predict_data.columns for col in required_cols):
                raise Exception("CSV file must contain columns: sensor1_resistance, sensor2_resistance, sensor3_resistance")
            
            if len(predict_data) == 0:
                raise Exception("CSV file is empty")
                
            # 生成衍生特征
            predict_data['resistance_avg'] = predict_data[required_cols].mean(axis=1)
            predict_data['resistance_std'] = predict_data[required_cols].std(axis=1)
            
            # 创建特征矩阵
            X_predict = predict_data[features]
            
            # 标准化特征
            X_predict_scaled = scaler.transform(X_predict)
            X_predict_scaled_df = pd.DataFrame(X_predict_scaled, columns=features)
            
            # 进行预测
            dia_pred = rf_dia.predict(X_predict_scaled_df)
            ht_pred = rf_ht.predict(X_predict_scaled_df)
            wt_pred = rf_wt.predict(X_predict_scaled_df)
            
            return dia_pred, ht_pred, wt_pred
            
        except Exception as e:
            raise Exception(f"Prediction error: {str(e)}")

    def on_closing(self):
        """关闭窗口时清理资源"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.root.destroy()


# 以下是Piper SDK相关的函数
def enable_fun(piper:C_PiperInterface):
    '''
    使能机械臂并检测使能状态,尝试5s,如果使能超时则退出程序
    '''
    enable_flag = False
    # 设置超时时间（秒）
    timeout = 5
    # 记录进入循环前的时间
    start_time = time.time()
    elapsed_time_flag = False
    while not (enable_flag):
        elapsed_time = time.time() - start_time
        print("--------------------")
        enable_flag = piper.GetArmLowSpdInfoMsgs().motor_1.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_2.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_3.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_4.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_5.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_6.foc_status.driver_enable_status
        print("Enable status:",enable_flag)
        piper.EnableArm(7)
        piper.GripperCtrl(0,1000,0x01, 0)
        print("--------------------")
        # 检查是否超过超时时间
        if elapsed_time > timeout:
            print("Timeout....")
            elapsed_time_flag = True
            enable_flag = True
            break
        time.sleep(1)
        pass
    if(elapsed_time_flag):
        print("Enable timeout, exiting program")
        exit(0)


def endpose(coords):
    if len(coords) != 6:
        raise ValueError("Coordinate parameters must include 6 numbers")
    piper = C_PiperInterface("can0")
    piper.ConnectPort()
    piper.EnableArm(7)
    enable_fun(piper=piper)
    factor = 1000
    # 坐标转换
    scaled_coords = [round(c * factor) for c in coords]
    X, Y, Z, RX, RY, RZ = scaled_coords
    piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)
    piper.EndPoseCtrl(X,Y,Z,RX,RY,RZ)
    print(f"Robot arm moved to position: {coords}")
    print(piper.GetArmEndPoseMsgs())
    
def gripperctrl(angle):
    piper = C_PiperInterface("can0")
    piper.ConnectPort()
    piper.EnableArm(7)
    piper.GripperCtrl(angle*1000,1000,0x01, 0)


if __name__ == "__main__":
    root = tk.Tk()
    app = TomatoClassifierApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()