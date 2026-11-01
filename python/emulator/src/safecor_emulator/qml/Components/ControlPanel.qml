import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import safecor.emulator 1.0

ScrollView {
    id: root
    clip: true

    ColumnLayout {
        width: root.width
        spacing: 8

        // --- Disks -------------------------------------------------------
        GroupBox {
            title: "Disks"
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
                            text: "Detach"
                            onClicked: ConsoleController.detach_disk(modelData)
                        }
                    }
                }

                RowLayout {
                    Text { text: "id:" }
                    TextField {
                        id: diskIdField
                        Layout.fillWidth: true
                        placeholderText: "disk id"
                    }
                    Button {
                        text: "Attach"
                        onClicked: ConsoleController.attach_disk(diskIdField.text, diskPathField.text)
                    }
                    TextField {
                        id: diskPathField
                        Layout.fillWidth: true
                        placeholderText: "root path"
                    }
                }
            }
        }

        // --- Energy ------------------------------------------------------
        GroupBox {
            title: "Energy"
            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                RowLayout {
                    Text { text: "Level:" }
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
                        text: "AC plugged"
                        checked: ConsoleController.plugged
                        onToggled: ConsoleController.set_energy(ConsoleController.energyLevel, checked)
                    }
                    Button { text: "Power off"; onClicked: ConsoleController.power_off() }
                    Button { text: "Power on"; onClicked: ConsoleController.power_on() }
                }
            }
        }

        // --- Language ----------------------------------------------------
        GroupBox {
            title: "Language"
            RowLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8

                Text { text: "Default:" }
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
            title: "Workflow"
            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                RowLayout {
                    Text { text: "Restart domain:" }
                    TextField {
                        id: restartNameField
                        Layout.fillWidth: true
                        placeholderText: "domain name"
                    }
                    Button {
                        text: "Restart"
                        onClicked: ConsoleController.restart_domain(restartNameField.text)
                    }
                }
                RowLayout {
                    Button {
                        text: "Shutdown (W2)"
                        Layout.fillWidth: true
                        onClicked: ConsoleController.shutdown()
                    }
                    Button {
                        text: "GUI ready (W4)"
                        Layout.fillWidth: true
                        onClicked: ConsoleController.gui_ready()
                    }
                }
                RowLayout {
                    Text { text: "Switch GUI to:" }
                    TextField {
                        id: switchGuiField
                        Layout.fillWidth: true
                        placeholderText: "domain"
                    }
                    Button {
                        text: "Switch (W5)"
                        onClicked: ConsoleController.switch_gui(switchGuiField.text)
                    }
                }
            }
        }

        // --- Logging -----------------------------------------------------
        GroupBox {
            title: "Logging"
            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 4

                RowLayout {
                    Text { text: "Level:" }
                    ComboBox {
                        id: logLevelCombo
                        Layout.fillWidth: true
                        model: ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                        onActivated: ConsoleController.set_loglevel(currentText)
                    }
                }
                RowLayout {
                    Text { text: "Save log:" }
                    TextField { id: saveLogDiskField; placeholderText: "disk" }
                    TextField { id: saveLogFileField; placeholderText: "file" }
                    Button {
                        text: "Save"
                        onClicked: ConsoleController.save_log(saveLogDiskField.text, saveLogFileField.text)
                    }
                }
                RowLayout {
                    Text { text: "Record journal:" }
                    TextField {
                        id: recordJournalField
                        Layout.fillWidth: true
                        placeholderText: "path (empty = stop)"
                    }
                    Button {
                        text: "Set"
                        onClicked: ConsoleController.set_record_journal(recordJournalField.text)
                    }
                }
                RowLayout {
                    Text { text: "Record events:" }
                    TextField {
                        id: recordEventsField
                        Layout.fillWidth: true
                        placeholderText: "path (empty = stop)"
                    }
                    Button {
                        text: "Set"
                        onClicked: ConsoleController.set_record_events(recordEventsField.text)
                    }
                }
            }
        }

        // --- Debug -------------------------------------------------------
        GroupBox {
            title: "Debug"
            RowLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.leftMargin: 8
                anchors.rightMargin: 8

                Text { text: "Ping:" }
                TextField {
                    id: pingTargetField
                    placeholderText: "target"
                }
                TextField {
                    id: pingDataField
                    Layout.fillWidth: true
                    placeholderText: "data"
                }
                Button {
                    text: "Ping"
                    onClicked: ConsoleController.ping(pingTargetField.text, pingDataField.text)
                }
            }
        }
    }
}
