# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'SettingsDialog.ui'
#
# Created by: PyQt5 UI code generator 5.13.2
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_DialogSettings(object):
    def setupUi(self, DialogSettings):
        DialogSettings.setObjectName("DialogSettings")
        DialogSettings.resize(503, 789)
        self.verticalLayout = QtWidgets.QVBoxLayout(DialogSettings)
        self.verticalLayout.setObjectName("verticalLayout")
        self.toolBox = QtWidgets.QToolBox(DialogSettings)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.toolBox.sizePolicy().hasHeightForWidth())
        self.toolBox.setSizePolicy(sizePolicy)
        self.toolBox.setObjectName("toolBox")
        self.pageApp = QtWidgets.QWidget()
        self.pageApp.setGeometry(QtCore.QRect(0, 0, 485, 685))
        self.pageApp.setMinimumSize(QtCore.QSize(0, 685))
        self.pageApp.setObjectName("pageApp")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.pageApp)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.label = QtWidgets.QLabel(self.pageApp)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        self.label.setObjectName("label")
        self.gridLayout_2.addWidget(self.label, 0, 0, 1, 2)
        self.lineEditApplicationName = QtWidgets.QLineEdit(self.pageApp)
        self.lineEditApplicationName.setObjectName("lineEditApplicationName")
        self.gridLayout_2.addWidget(self.lineEditApplicationName, 0, 2, 1, 1)
        self.label_2 = QtWidgets.QLabel(self.pageApp)
        self.label_2.setObjectName("label_2")
        self.gridLayout_2.addWidget(self.label_2, 1, 0, 1, 1)
        self.doubleSpinBoxDuration = QtWidgets.QDoubleSpinBox(self.pageApp)
        self.doubleSpinBoxDuration.setObjectName("doubleSpinBoxDuration")
        self.gridLayout_2.addWidget(self.doubleSpinBoxDuration, 1, 2, 1, 1)
        self.label_3 = QtWidgets.QLabel(self.pageApp)
        self.label_3.setObjectName("label_3")
        self.gridLayout_2.addWidget(self.label_3, 2, 0, 1, 1)
        self.doubleSpinBoxPreamble = QtWidgets.QDoubleSpinBox(self.pageApp)
        self.doubleSpinBoxPreamble.setObjectName("doubleSpinBoxPreamble")
        self.gridLayout_2.addWidget(self.doubleSpinBoxPreamble, 2, 2, 1, 1)
        self.label_5 = QtWidgets.QLabel(self.pageApp)
        self.label_5.setObjectName("label_5")
        self.gridLayout_2.addWidget(self.label_5, 3, 0, 1, 2)
        self.checkBoxDrawGraph = QtWidgets.QCheckBox(self.pageApp)
        self.checkBoxDrawGraph.setObjectName("checkBoxDrawGraph")
        self.gridLayout_2.addWidget(self.checkBoxDrawGraph, 3, 2, 1, 1)
        self.label_4 = QtWidgets.QLabel(self.pageApp)
        self.label_4.setObjectName("label_4")
        self.gridLayout_2.addWidget(self.label_4, 4, 0, 1, 1)
        self.frame = QtWidgets.QFrame(self.pageApp)
        self.frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setObjectName("frame")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.frame)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.checkBoxSyslogger = QtWidgets.QCheckBox(self.frame)
        self.checkBoxSyslogger.setObjectName("checkBoxSyslogger")
        self.verticalLayout_2.addWidget(self.checkBoxSyslogger)
        self.checkBoxBinderTransaction = QtWidgets.QCheckBox(self.frame)
        self.checkBoxBinderTransaction.setObjectName("checkBoxBinderTransaction")
        self.verticalLayout_2.addWidget(self.checkBoxBinderTransaction)
        self.checkBoxSchedSwitch = QtWidgets.QCheckBox(self.frame)
        self.checkBoxSchedSwitch.setObjectName("checkBoxSchedSwitch")
        self.verticalLayout_2.addWidget(self.checkBoxSchedSwitch)
        self.checkBoxCPUIdle = QtWidgets.QCheckBox(self.frame)
        self.checkBoxCPUIdle.setObjectName("checkBoxCPUIdle")
        self.verticalLayout_2.addWidget(self.checkBoxCPUIdle)
        self.checkBoxWakeUp = QtWidgets.QCheckBox(self.frame)
        self.checkBoxWakeUp.setObjectName("checkBoxWakeUp")
        self.verticalLayout_2.addWidget(self.checkBoxWakeUp)
        self.gridLayout_2.addWidget(self.frame, 4, 2, 1, 1)
        self.label_13 = QtWidgets.QLabel(self.pageApp)
        self.label_13.setObjectName("label_13")
        self.gridLayout_2.addWidget(self.label_13, 5, 0, 1, 1)
        self.frame_6 = QtWidgets.QFrame(self.pageApp)
        self.frame_6.setMinimumSize(QtCore.QSize(0, 257))
        self.frame_6.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_6.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_6.setObjectName("frame_6")
        self.verticalLayout_9 = QtWidgets.QVBoxLayout(self.frame_6)
        self.verticalLayout_9.setObjectName("verticalLayout_9")
        self.radioButtonNonthreaded = QtWidgets.QRadioButton(self.frame_6)
        self.radioButtonNonthreaded.setObjectName("radioButtonNonthreaded")
        self.verticalLayout_9.addWidget(self.radioButtonNonthreaded)
        self.radioButtonMultiThreaded = QtWidgets.QRadioButton(self.frame_6)
        self.radioButtonMultiThreaded.setObjectName("radioButtonMultiThreaded")
        self.verticalLayout_9.addWidget(self.radioButtonMultiThreaded)
        self.radioButtonMultiProcessing = QtWidgets.QRadioButton(self.frame_6)
        self.radioButtonMultiProcessing.setChecked(True)
        self.radioButtonMultiProcessing.setObjectName("radioButtonMultiProcessing")
        self.verticalLayout_9.addWidget(self.radioButtonMultiProcessing)
        self.gridLayout_2.addWidget(self.frame_6, 5, 2, 1, 1)
        self.label_14 = QtWidgets.QLabel(self.pageApp)
        self.label_14.setObjectName("label_14")
        self.gridLayout_2.addWidget(self.label_14, 6, 0, 1, 1)
        self.checkBoxUseUIConsole = QtWidgets.QCheckBox(self.pageApp)
        self.checkBoxUseUIConsole.setChecked(True)
        self.checkBoxUseUIConsole.setObjectName("checkBoxUseUIConsole")
        self.gridLayout_2.addWidget(self.checkBoxUseUIConsole, 6, 2, 1, 1)
        self.toolBox.addItem(self.pageApp, "")
        self.pageSyslogger = QtWidgets.QWidget()
        self.pageSyslogger.setGeometry(QtCore.QRect(0, 0, 485, 685))
        self.pageSyslogger.setObjectName("pageSyslogger")
        self.gridLayout_3 = QtWidgets.QGridLayout(self.pageSyslogger)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.label_6 = QtWidgets.QLabel(self.pageSyslogger)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_6.sizePolicy().hasHeightForWidth())
        self.label_6.setSizePolicy(sizePolicy)
        self.label_6.setObjectName("label_6")
        self.gridLayout_3.addWidget(self.label_6, 0, 0, 1, 1)
        self.frame_2 = QtWidgets.QFrame(self.pageSyslogger)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy)
        self.frame_2.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_2.setObjectName("frame_2")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self.frame_2)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.checkBoxTraceThreads = QtWidgets.QCheckBox(self.frame_2)
        self.checkBoxTraceThreads.setChecked(True)
        self.checkBoxTraceThreads.setObjectName("checkBoxTraceThreads")
        self.verticalLayout_5.addWidget(self.checkBoxTraceThreads)
        self.checkBoxChromeGovernor = QtWidgets.QCheckBox(self.frame_2)
        self.checkBoxChromeGovernor.setObjectName("checkBoxChromeGovernor")
        self.verticalLayout_5.addWidget(self.checkBoxChromeGovernor)
        self.gridLayout_3.addWidget(self.frame_2, 0, 1, 1, 1)
        self.label_7 = QtWidgets.QLabel(self.pageSyslogger)
        self.label_7.setObjectName("label_7")
        self.gridLayout_3.addWidget(self.label_7, 1, 0, 1, 1)
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.pushButtonSysloggerSetup = QtWidgets.QPushButton(self.pageSyslogger)
        self.pushButtonSysloggerSetup.setObjectName("pushButtonSysloggerSetup")
        self.gridLayout.addWidget(self.pushButtonSysloggerSetup, 0, 0, 1, 1)
        self.pushButtonSysloggerStart = QtWidgets.QPushButton(self.pageSyslogger)
        self.pushButtonSysloggerStart.setObjectName("pushButtonSysloggerStart")
        self.gridLayout.addWidget(self.pushButtonSysloggerStart, 0, 1, 1, 1)
        self.pushButtonSysloggerStop = QtWidgets.QPushButton(self.pageSyslogger)
        self.pushButtonSysloggerStop.setObjectName("pushButtonSysloggerStop")
        self.gridLayout.addWidget(self.pushButtonSysloggerStop, 1, 0, 1, 1)
        self.pushButtonSysloggerFinish = QtWidgets.QPushButton(self.pageSyslogger)
        self.pushButtonSysloggerFinish.setObjectName("pushButtonSysloggerFinish")
        self.gridLayout.addWidget(self.pushButtonSysloggerFinish, 1, 1, 1, 1)
        self.gridLayout_3.addLayout(self.gridLayout, 1, 1, 1, 1)
        self.label_8 = QtWidgets.QLabel(self.pageSyslogger)
        self.label_8.setObjectName("label_8")
        self.gridLayout_3.addWidget(self.label_8, 2, 0, 1, 1)
        self.frame_5 = QtWidgets.QFrame(self.pageSyslogger)
        self.frame_5.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_5.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_5.setObjectName("frame_5")
        self.verticalLayout_8 = QtWidgets.QVBoxLayout(self.frame_5)
        self.verticalLayout_8.setObjectName("verticalLayout_8")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.lineEditSyslogPullFolder = QtWidgets.QLineEdit(self.frame_5)
        self.lineEditSyslogPullFolder.setClearButtonEnabled(True)
        self.lineEditSyslogPullFolder.setObjectName("lineEditSyslogPullFolder")
        self.horizontalLayout.addWidget(self.lineEditSyslogPullFolder)
        self.pushButtonChoosePullFile = QtWidgets.QPushButton(self.frame_5)
        self.pushButtonChoosePullFile.setText("")
        icon = QtGui.QIcon()
        icon.addPixmap(
            QtGui.QPixmap("../icons/folder.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off
        )
        self.pushButtonChoosePullFile.setIcon(icon)
        self.pushButtonChoosePullFile.setObjectName("pushButtonChoosePullFile")
        self.horizontalLayout.addWidget(self.pushButtonChoosePullFile)
        self.pushButtonSysloggerPull = QtWidgets.QPushButton(self.frame_5)
        self.pushButtonSysloggerPull.setObjectName("pushButtonSysloggerPull")
        self.horizontalLayout.addWidget(self.pushButtonSysloggerPull)
        self.verticalLayout_8.addLayout(self.horizontalLayout)
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.lineEditSyslogPullFilename = QtWidgets.QLineEdit(self.frame_5)
        self.lineEditSyslogPullFilename.setObjectName("lineEditSyslogPullFilename")
        self.horizontalLayout_4.addWidget(self.lineEditSyslogPullFilename)
        self.verticalLayout_8.addLayout(self.horizontalLayout_4)
        self.gridLayout_3.addWidget(self.frame_5, 2, 1, 1, 1)
        self.label_9 = QtWidgets.QLabel(self.pageSyslogger)
        self.label_9.setObjectName("label_9")
        self.gridLayout_3.addWidget(self.label_9, 3, 0, 1, 1)
        self.frame_3 = QtWidgets.QFrame(self.pageSyslogger)
        self.frame_3.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_3.setObjectName("frame_3")
        self.verticalLayout_6 = QtWidgets.QVBoxLayout(self.frame_3)
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.lineEditConvertSource = QtWidgets.QLineEdit(self.frame_3)
        self.lineEditConvertSource.setObjectName("lineEditConvertSource")
        self.horizontalLayout_2.addWidget(self.lineEditConvertSource)
        self.pushButtonFileToConvert = QtWidgets.QPushButton(self.frame_3)
        self.pushButtonFileToConvert.setText("")
        self.pushButtonFileToConvert.setIcon(icon)
        self.pushButtonFileToConvert.setObjectName("pushButtonFileToConvert")
        self.horizontalLayout_2.addWidget(self.pushButtonFileToConvert)
        self.verticalLayout_6.addLayout(self.horizontalLayout_2)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.lineEditConvertDestination = QtWidgets.QLineEdit(self.frame_3)
        self.lineEditConvertDestination.setObjectName("lineEditConvertDestination")
        self.horizontalLayout_3.addWidget(self.lineEditConvertDestination)
        self.pushButtonFileToConvertDestination = QtWidgets.QPushButton(self.frame_3)
        self.pushButtonFileToConvertDestination.setText("")
        self.pushButtonFileToConvertDestination.setIcon(icon)
        self.pushButtonFileToConvertDestination.setObjectName(
            "pushButtonFileToConvertDestination"
        )
        self.horizontalLayout_3.addWidget(self.pushButtonFileToConvertDestination)
        self.verticalLayout_6.addLayout(self.horizontalLayout_3)
        self.pushButtonConvertTrace = QtWidgets.QPushButton(self.frame_3)
        self.pushButtonConvertTrace.setObjectName("pushButtonConvertTrace")
        self.verticalLayout_6.addWidget(self.pushButtonConvertTrace)
        self.gridLayout_3.addWidget(self.frame_3, 3, 1, 1, 1)
        self.label_10 = QtWidgets.QLabel(self.pageSyslogger)
        self.label_10.setObjectName("label_10")
        self.gridLayout_3.addWidget(self.label_10, 4, 0, 1, 1)
        self.spinBoxCPU = QtWidgets.QSpinBox(self.pageSyslogger)
        self.spinBoxCPU.setMaximum(7)
        self.spinBoxCPU.setProperty("value", 2)
        self.spinBoxCPU.setObjectName("spinBoxCPU")
        self.gridLayout_3.addWidget(self.spinBoxCPU, 4, 1, 1, 1)
        self.label_11 = QtWidgets.QLabel(self.pageSyslogger)
        self.label_11.setObjectName("label_11")
        self.gridLayout_3.addWidget(self.label_11, 5, 0, 1, 1)
        self.spinBoxInterval = QtWidgets.QSpinBox(self.pageSyslogger)
        self.spinBoxInterval.setObjectName("spinBoxInterval")
        self.gridLayout_3.addWidget(self.spinBoxInterval, 5, 1, 1, 1)
        self.label_12 = QtWidgets.QLabel(self.pageSyslogger)
        self.label_12.setObjectName("label_12")
        self.gridLayout_3.addWidget(self.label_12, 6, 0, 1, 1)
        self.frame_4 = QtWidgets.QFrame(self.pageSyslogger)
        self.frame_4.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame_4.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame_4.setObjectName("frame_4")
        self.verticalLayout_7 = QtWidgets.QVBoxLayout(self.frame_4)
        self.verticalLayout_7.setObjectName("verticalLayout_7")
        self.checkBoxCPUInfo = QtWidgets.QCheckBox(self.frame_4)
        self.checkBoxCPUInfo.setChecked(True)
        self.checkBoxCPUInfo.setObjectName("checkBoxCPUInfo")
        self.verticalLayout_7.addWidget(self.checkBoxCPUInfo)
        self.checkBoxCPUFrequency = QtWidgets.QCheckBox(self.frame_4)
        self.checkBoxCPUFrequency.setChecked(True)
        self.checkBoxCPUFrequency.setObjectName("checkBoxCPUFrequency")
        self.verticalLayout_7.addWidget(self.checkBoxCPUFrequency)
        self.checkBoxPower = QtWidgets.QCheckBox(self.frame_4)
        self.checkBoxPower.setChecked(True)
        self.checkBoxPower.setObjectName("checkBoxPower")
        self.verticalLayout_7.addWidget(self.checkBoxPower)
        self.checkBoxMali = QtWidgets.QCheckBox(self.frame_4)
        self.checkBoxMali.setChecked(True)
        self.checkBoxMali.setObjectName("checkBoxMali")
        self.verticalLayout_7.addWidget(self.checkBoxMali)
        self.checkBoxTemp = QtWidgets.QCheckBox(self.frame_4)
        self.checkBoxTemp.setChecked(True)
        self.checkBoxTemp.setObjectName("checkBoxTemp")
        self.verticalLayout_7.addWidget(self.checkBoxTemp)
        self.checkBoxNetwork = QtWidgets.QCheckBox(self.frame_4)
        self.checkBoxNetwork.setObjectName("checkBoxNetwork")
        self.verticalLayout_7.addWidget(self.checkBoxNetwork)
        self.gridLayout_3.addWidget(self.frame_4, 6, 1, 1, 1)
        self.toolBox.addItem(self.pageSyslogger, "")
        self.verticalLayout.addWidget(self.toolBox)
        self.buttonBox = QtWidgets.QDialogButtonBox(DialogSettings)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok
        )
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(DialogSettings)
        self.toolBox.setCurrentIndex(0)
        self.buttonBox.accepted.connect(DialogSettings.accept)
        self.pushButtonSysloggerPull.clicked.connect(
            DialogSettings.sysloggerpull_clicked
        )
        self.pushButtonChoosePullFile.clicked.connect(
            DialogSettings.sysloggerpullfile_clicked
        )
        self.pushButtonSysloggerStart.clicked.connect(
            DialogSettings.sysloggerstart_clicked
        )
        self.pushButtonSysloggerSetup.clicked.connect(
            DialogSettings.sysloggersetup_clicked
        )
        self.pushButtonSysloggerStop.clicked.connect(
            DialogSettings.sysloggerstop_clicked
        )
        self.pushButtonSysloggerFinish.clicked.connect(
            DialogSettings.sysloggerfinish_clicked
        )
        self.pushButtonFileToConvert.clicked.connect(
            DialogSettings.sysloggerfiletoconvert_clicked
        )
        self.pushButtonConvertTrace.clicked.connect(
            DialogSettings.sysloggerconverttrace_clicked
        )
        self.pushButtonFileToConvertDestination.clicked.connect(
            DialogSettings.sysloggerfiletoconvertdestination_clicked
        )
        self.buttonBox.rejected.connect(DialogSettings.reject)
        QtCore.QMetaObject.connectSlotsByName(DialogSettings)

    def retranslateUi(self, DialogSettings):
        _translate = QtCore.QCoreApplication.translate
        DialogSettings.setWindowTitle(_translate("DialogSettings", "Settings"))
        self.label.setText(_translate("DialogSettings", "Default Application Name"))
        self.label_2.setText(_translate("DialogSettings", "Default Duration"))
        self.label_3.setText(_translate("DialogSettings", "Default Preamble"))
        self.label_5.setText(_translate("DialogSettings", "Draw Graph by  Default"))
        self.checkBoxDrawGraph.setText(_translate("DialogSettings", "Draw Graph"))
        self.label_4.setText(_translate("DialogSettings", "Default Events"))
        self.checkBoxSyslogger.setText(_translate("DialogSettings", "Syslogger"))
        self.checkBoxBinderTransaction.setText(
            _translate("DialogSettings", "Binder Transaction")
        )
        self.checkBoxSchedSwitch.setText(_translate("DialogSettings", "Sched Switch"))
        self.checkBoxCPUIdle.setText(_translate("DialogSettings", "CPU Idle"))
        self.checkBoxWakeUp.setText(_translate("DialogSettings", "Wake Up"))
        self.label_13.setText(_translate("DialogSettings", "Speed Optimizations"))
        self.radioButtonNonthreaded.setText(
            _translate("DialogSettings", "No threading (application will block)")
        )
        self.radioButtonMultiThreaded.setText(
            _translate("DialogSettings", "Multi threaded")
        )
        self.radioButtonMultiProcessing.setText(
            _translate("DialogSettings", "Multi processing")
        )
        self.label_14.setText(
            _translate(
                "DialogSettings", "Use UI Console<br>Only usable with mutlithreading"
            )
        )
        self.checkBoxUseUIConsole.setText(
            _translate("DialogSettings", "Enabled (restart required)")
        )
        self.toolBox.setItemText(
            self.toolBox.indexOf(self.pageApp),
            _translate("DialogSettings", "Application"),
        )
        self.label_6.setText(_translate("DialogSettings", "Flags"))
        self.checkBoxTraceThreads.setToolTip(
            _translate(
                "DialogSettings",
                "can be specified to disable tracing of threads (runtime and CPU asignment), and therefore to minimize overhead when only wanting to trace e.g. power consumption",
            )
        )
        self.checkBoxTraceThreads.setText(_translate("DialogSettings", "Trace Threads"))
        self.checkBoxChromeGovernor.setToolTip(
            _translate(
                "DialogSettings",
                "instructs trace-cmd to also enable and trace tracepoints implemented by the chrome governor",
            )
        )
        self.checkBoxChromeGovernor.setText(
            _translate("DialogSettings", "Chrome Governor")
        )
        self.label_7.setText(
            _translate("DialogSettings", "Manal Syslogger<br> Commands")
        )
        self.pushButtonSysloggerSetup.setText(_translate("DialogSettings", "Setup"))
        self.pushButtonSysloggerStart.setText(_translate("DialogSettings", "Start"))
        self.pushButtonSysloggerStop.setText(_translate("DialogSettings", "Stop"))
        self.pushButtonSysloggerFinish.setText(_translate("DialogSettings", "Finish"))
        self.label_8.setText(
            _translate("DialogSettings", "Pull Syslogger <br>Data to Folder")
        )
        self.lineEditSyslogPullFolder.setPlaceholderText(
            _translate("DialogSettings", "Destination folder")
        )
        self.pushButtonSysloggerPull.setText(_translate("DialogSettings", "Pull"))
        self.lineEditSyslogPullFilename.setPlaceholderText(
            _translate("DialogSettings", "New file name")
        )
        self.label_9.setText(_translate("DialogSettings", "Process Tracecmd<br>File"))
        self.lineEditConvertSource.setPlaceholderText(
            _translate("DialogSettings", "Input file")
        )
        self.lineEditConvertDestination.setPlaceholderText(
            _translate("DialogSettings", "Destination folder")
        )
        self.pushButtonConvertTrace.setText(_translate("DialogSettings", "Process"))
        self.label_10.setToolTip(
            _translate("DialogSettings", "CPU to run/pin the logging thread on")
        )
        self.label_10.setText(_translate("DialogSettings", "Logging Thread <br>CPU"))
        self.label_11.setText(_translate("DialogSettings", "Interval"))
        self.label_12.setText(
            _translate("DialogSettings", "System Properties<br>to Trace")
        )
        self.checkBoxCPUInfo.setToolTip(
            _translate("DialogSettings", "Log CPU system/user/idle time and state")
        )
        self.checkBoxCPUInfo.setText(_translate("DialogSettings", "CPU Information"))
        self.checkBoxCPUFrequency.setToolTip(
            _translate(
                "DialogSettings",
                "Log CPU frequency for each first CPU in a policy group",
            )
        )
        self.checkBoxCPUFrequency.setText(_translate("DialogSettings", "CPU Frequency"))
        self.checkBoxPower.setToolTip(
            _translate("DialogSettings", "Log Power consumption via ina231 sensors")
        )
        self.checkBoxPower.setText(_translate("DialogSettings", "INA231 Power"))
        self.checkBoxMali.setToolTip(
            _translate("DialogSettings", "Log mali GPU information")
        )
        self.checkBoxMali.setText(_translate("DialogSettings", "Mali GPU"))
        self.checkBoxTemp.setToolTip(
            _translate("DialogSettings", "Log CPU and GPU temperature on Exynos boards")
        )
        self.checkBoxTemp.setText(
            _translate("DialogSettings", "CPU and GPU Temperature")
        )
        self.checkBoxNetwork.setToolTip(
            _translate("DialogSettings", "Log network interface rx/tx stats")
        )
        self.checkBoxNetwork.setText(_translate("DialogSettings", "Network Rx/Tx"))
        self.toolBox.setItemText(
            self.toolBox.indexOf(self.pageSyslogger),
            _translate("DialogSettings", "Syslogger"),
        )
