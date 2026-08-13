import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".." as AppTheme

Item {
    id: page
    objectName: "backupsPage"
    property var controller
    property var backups: controller ? controller.backups : null
    property var shell
    readonly property bool wideLayout: width >= 1000
    readonly property bool selectionEnabled: backups && backups.state === "ready" && backups.mutationState === "idle" && !(shell && shell.backupDialogVisible)

    ScrollView {
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width - AppTheme.Theme.space24 * 2
            x: AppTheme.Theme.space24
            spacing: AppTheme.Theme.space20

            AppCard {
                Layout.fillWidth: true
                implicitHeight: headerColumn.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: headerColumn
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space12
                    SectionHeader {
                        Layout.fillWidth: true
                        title: "Custódia de backups"
                        subtitle: "Escolha um registro imutável antes de restaurar ou excluir"
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: AppTheme.Theme.space12
                        AppButton {
                            objectName: "createBackupButton"
                            text: "Criar backup"
                            tooltipText: "Criar backup do save selecionado"
                            variant: "primary"
                            enabled: backups && backups.canCreate
                            onClicked: backups.createForSelectedSlot()
                        }
                        Item { Layout.fillWidth: true }
                        AppButton {
                            objectName: "restoreBackupButton"
                            text: "Restaurar"
                            tooltipText: "Restaurar o backup selecionado"
                            enabled: backups && backups.canRestore
                            onClicked: backups.requestRestore()
                        }
                        AppButton {
                            objectName: "deleteBackupButton"
                            text: "Excluir"
                            tooltipText: "Excluir o backup selecionado"
                            variant: "danger"
                            enabled: backups && backups.canDelete
                            onClicked: backups.requestDelete()
                        }
                    }
                    InlineMessage {
                        objectName: "backupsErrorMessage"
                        Layout.fillWidth: true
                        visible: backups && backups.state === "error"
                        severity: "error"
                        message: backups ? backups.errorMessage : ""
                    }
                    InlineMessage {
                        objectName: "backupsStatusMessage"
                        Layout.fillWidth: true
                        visible: backups && backups.statusMessage.length > 0 && backups.state !== "error"
                        severity: "success"
                        message: backups ? backups.statusMessage : ""
                    }
                }
            }

            AppCard {
                Layout.fillWidth: true
                implicitHeight: recordsColumn.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: recordsColumn
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space12
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Registros sob custódia"
                            color: AppTheme.Theme.textPrimary
                            font.family: AppTheme.Theme.displayFont
                            font.pixelSize: AppTheme.Theme.typeCardTitle
                            font.weight: AppTheme.Theme.weightBold
                            Layout.fillWidth: true
                        }
                        Text {
                            objectName: "backupIdentityLabel"
                            text: backups && backups.selectedBackupId.length > 0 ? backups.selectedBackupId : "Nenhum backup selecionado"
                            color: AppTheme.Theme.textMuted
                            font.family: AppTheme.Theme.utilityFont
                            font.pixelSize: AppTheme.Theme.typeMeta
                            elide: Text.ElideMiddle
                            Layout.maximumWidth: page.wideLayout ? 340 : 210
                        }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: AppTheme.Theme.borderWidth; color: AppTheme.Theme.border }
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: backups && backups.state === "ready" ? Math.max(AppTheme.Theme.primaryActionHeight * 2, backupsList.contentHeight) : AppTheme.Theme.primaryActionHeight * 3
                        ListView {
                            id: backupsList
                            objectName: "backupsList"
                            anchors.fill: parent
                            clip: true
                            visible: backups && backups.state === "ready"
                            interactive: page.selectionEnabled
                            model: backups ? backups.backupsModel : null
                            spacing: AppTheme.Theme.space8
                            delegate: Button {
                                id: backupDelegate
                                objectName: "backupRecord-" + backupId
                                required property string backupId
                                required property string slotId
                                required property string slotLabel
                                required property string createdAtLabel
                                required property string sizeLabel
                                required property string integrityLabel
                                required property bool selected
                                width: backupsList.width
                                implicitHeight: page.wideLayout ? 64 : 112
                                enabled: page.selectionEnabled
                                focusPolicy: Qt.StrongFocus
                                Accessible.name: slotLabel + ", " + createdAtLabel + ", " + integrityLabel
                                onClicked: backups.selectBackup(backupId)
                                background: Rectangle {
                                    radius: AppTheme.Theme.radiusControl
                                    color: backupDelegate.hovered || backupDelegate.selected ? AppTheme.Theme.surfaceRaised : AppTheme.Theme.surface
                                    border.width: AppTheme.Theme.borderWidth
                                    border.color: backupDelegate.activeFocus ? AppTheme.Theme.focus : (backupDelegate.selected ? AppTheme.Theme.accent : AppTheme.Theme.border)
                                    Rectangle {
                                        anchors.left: parent.left
                                        anchors.leftMargin: AppTheme.Theme.space8
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: AppTheme.Theme.space4
                                        height: backupDelegate.selected ? parent.height - AppTheme.Theme.space24 : AppTheme.Theme.space12
                                        radius: width
                                        color: backupDelegate.selected ? AppTheme.Theme.accent : AppTheme.Theme.border
                                    }
                                }
                                contentItem: Loader {
                                    anchors.fill: parent
                                    anchors.leftMargin: AppTheme.Theme.space24
                                    anchors.rightMargin: AppTheme.Theme.space16
                                    sourceComponent: page.wideLayout ? wideRecord : narrowRecord
                                }
                                Component {
                                    id: wideRecord
                                    RowLayout {
                                        spacing: AppTheme.Theme.space16
                                        Text { text: backupDelegate.slotLabel; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; font.weight: AppTheme.Theme.weightSemibold; Layout.preferredWidth: 130 }
                                        Text { text: backupDelegate.createdAtLabel; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta; Layout.fillWidth: true }
                                        Text { text: backupDelegate.sizeLabel; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta; Layout.preferredWidth: 88; horizontalAlignment: Text.AlignRight }
                                        Rectangle {
                                            Layout.preferredWidth: 126; Layout.preferredHeight: AppTheme.Theme.controlHeight
                                            radius: AppTheme.Theme.radiusControl; color: AppTheme.Theme.surfaceMuted
                                            Text { anchors.centerIn: parent; text: backupDelegate.integrityLabel; color: AppTheme.Theme.success; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta }
                                        }
                                        Text { text: backupDelegate.backupId; color: AppTheme.Theme.textMuted; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta; Layout.preferredWidth: 170; elide: Text.ElideMiddle }
                                    }
                                }
                                Component {
                                    id: narrowRecord
                                    ColumnLayout {
                                        spacing: AppTheme.Theme.space4
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Text { text: backupDelegate.slotLabel; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; font.weight: AppTheme.Theme.weightSemibold; Layout.fillWidth: true }
                                            Text { text: backupDelegate.integrityLabel; color: AppTheme.Theme.success; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta }
                                        }
                                        Text { text: backupDelegate.createdAtLabel + " · " + backupDelegate.sizeLabel; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeMeta }
                                        Text { text: backupDelegate.backupId; color: AppTheme.Theme.textMuted; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                    }
                                }
                            }
                        }
                        ColumnLayout {
                            anchors.fill: parent
                            visible: !backups || backups.state !== "ready"
                            spacing: AppTheme.Theme.space8
                            Text {
                                text: backups && backups.state === "loading" ? "Lendo o livro de custódia…" : (backups && backups.state === "error" ? "Não foi possível carregar os backups." : "Nenhum backup encontrado.")
                                color: backups && backups.state === "error" ? AppTheme.Theme.error : AppTheme.Theme.textSecondary
                                font.family: AppTheme.Theme.bodyFont
                                font.pixelSize: AppTheme.Theme.typeBody
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                            AppButton { visible: backups && backups.state === "error"; text: "Tentar novamente"; onClicked: backups.refresh() }
                            Item { objectName: "backupsEmptyState"; visible: backups && backups.state === "empty"; Layout.preferredHeight: 0 }
                        }
                    }
                }
            }
        }
    }
}
