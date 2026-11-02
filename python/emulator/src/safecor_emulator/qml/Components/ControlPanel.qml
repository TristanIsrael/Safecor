import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import safecor.emulator 1.0

ScrollView {
    id: root
    clip: true

    ColumnLayout {
        width: root.width * 0.9

        spacing: 16

        // --- Disks -------------------------------------------------------
        GroupBox {
            title: qsTr("Disks")
            Layout.fillWidth: true

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                Repeater {
                    model: ConsoleController.disks
                    RowLayout {
                        Text { text: "• " + modelData }
                        Button {
                            text: qsTr("Detach")
                            onClicked: ConsoleController.detach_disk(modelData)
                        }
                    }
                }

                RowLayout {
                    Text { text: qsTr("id:") }
                    TextField {
                        id: diskIdField
                        Layout.fillWidth: true
                        placeholderText: qsTr("disk id")
                    }
                    TextField {
                        id: diskPathField
                        Layout.fillWidth: true
                        placeholderText: qsTr("root path")
                    }
                    Button {
                        text: qsTr("Attach")
                        onClicked: ConsoleController.attach_disk(diskIdField.text, diskPathField.text)
                    }
                }
            }
        }

        // --- Energy ------------------------------------------------------
        GroupBox {
            title: qsTr("Energy")
            Layout.fillWidth: true

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                RowLayout {
                    Text { text: qsTr("Level:") }
                    Slider {
                        id: energySlider
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        stepSize: 1
                        value: ConsoleController.energyLevel
                        onMoved: ConsoleController.set_energy(value, ConsoleController.plugged)
                    }
                    Text { text: Math.round(ConsoleController.energyLevel) + "%" }
                }
                RowLayout {
                    CheckBox {
                        id: pluggedCheck
                        text: qsTr("AC plugged")
                        checked: ConsoleController.plugged
                        onToggled: ConsoleController.set_energy(ConsoleController.energyLevel, checked)
                    }
                    Button { text: qsTr("Power off"); onClicked: ConsoleController.power_off() }
                    Button { text: qsTr("Power on"); onClicked: ConsoleController.power_on() }
                }
            }
        }

        // --- Language ----------------------------------------------------
        GroupBox {
            title: qsTr("Product language")
            Layout.fillWidth: true

            RowLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8

                Text { text: qsTr("Default:") }
                ComboBox {
                    id: languageCombo
                    Layout.fillWidth: true
                    model: ConsoleController.languages.length ? ConsoleController.languages : ["en"]
                    onActivated: ConsoleController.set_language(currentText)
                }
            }
        }

        // --- Workflow ----------------------------------------------------
        GroupBox {
            title: qsTr("Workflow")
            Layout.fillWidth: true

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                RowLayout {
                    Text { text: qsTr("Restart domain:") }
                    ComboBox {
                        id: restartDomainCombo
                        Layout.fillWidth: true
                        model: ConsoleController.businessDomains
                    }
                    Button {
                        text: qsTr("Restart")
                        onClicked: ConsoleController.restart_domain(restartDomainCombo.currentText)
                    }
                }
                RowLayout {
                    Button {
                        text: qsTr("Shutdown (W2)")
                        Layout.fillWidth: true
                        onClicked: ConsoleController.shutdown()
                    }
                    Button {
                        text: qsTr("GUI ready (W4)")
                        Layout.fillWidth: true
                        onClicked: ConsoleController.gui_ready()
                    }
                }
                RowLayout {
                    Text { text: qsTr("Switch GUI to:") }
                    ComboBox {
                        id: switchGuiCombo
                        Layout.fillWidth: true
                        model: ConsoleController.businessDomains
                    }
                    Button {
                        text: qsTr("Switch (W5)")
                        onClicked: ConsoleController.switch_gui(switchGuiCombo.currentText)
                    }
                }
            }
        }

        // --- Logging -----------------------------------------------------
        GroupBox {
            title: qsTr("Logging")
            Layout.fillWidth: true

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                RowLayout {
                    Text { text: qsTr("Level:") }
                    ComboBox {
                        id: logLevelCombo
                        Layout.fillWidth: true
                        model: ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                        onActivated: ConsoleController.set_loglevel(currentText)
                    }
                }
                RowLayout {
                    Text { text: qsTr("Save log:") }
                    ComboBox {
                        id: saveLogDiskCombo
                        Layout.preferredWidth: 120
                        model: ConsoleController.disks
                    }
                    TextField {
                        id: saveLogFileField
                        Layout.fillWidth: true
                        placeholderText: qsTr("file")
                    }
                    Button {
                        text: qsTr("Save")
                        onClicked: ConsoleController.save_log(saveLogDiskCombo.currentText, saveLogFileField.text)
                    }
                }
                RowLayout {
                    Text { text: qsTr("Record journal:") }
                    TextField {
                        id: recordJournalField
                        Layout.fillWidth: true
                        placeholderText: qsTr("path (empty = stop)")
                    }
                    Button {
                        text: qsTr("Set")
                        onClicked: ConsoleController.set_record_journal(recordJournalField.text)
                    }
                }
                RowLayout {
                    Text { text: qsTr("Record events:") }
                    TextField {
                        id: recordEventsField
                        Layout.fillWidth: true
                        placeholderText: qsTr("path (empty = stop)")
                    }
                    Button {
                        text: qsTr("Set")
                        onClicked: ConsoleController.set_record_events(recordEventsField.text)
                    }
                }
            }
        }

        // --- Debug -------------------------------------------------------
        GroupBox {
            title: qsTr("Debug")
            Layout.fillWidth: true

            RowLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8

                Text { text: qsTr("Ping:") }
                ComboBox {
                    id: pingTargetCombo
                    Layout.preferredWidth: 120
                    model: ConsoleController.businessDomains
                }
                TextField {
                    id: pingDataField
                    Layout.fillWidth: true
                    placeholderText: qsTr("data")
                }
                Button {
                    text: qsTr("Ping")
                    onClicked: ConsoleController.ping(pingTargetCombo.currentText, pingDataField.text)
                }
            }
        }
    }
}
