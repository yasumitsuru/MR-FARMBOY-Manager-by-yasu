import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".." as AppTheme

Item {
    id: page
    objectName: "dashboardPage"
    property var controller
    property var shell
    property var dashboard: controller ? controller.dashboard : null
    property var saves: controller ? controller.saves : null

    ScrollView {
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width - AppTheme.Theme.space24 * 2
            x: AppTheme.Theme.space24
            spacing: AppTheme.Theme.space24

            SectionHeader {
                Layout.fillWidth: true
                title: "Caderno do cultivo"
                subtitle: dashboard && dashboard.configurationState === "valid" ? "Leitura atual do campo selecionado" : "Defina a origem dos saves para iniciar a leitura"
                StatusBadge {
                    status: dashboard && dashboard.configurationState === "valid" ? "success" : "warning"
                    label: dashboard && dashboard.configurationState === "valid" ? "Configuração ativa" : "Configuração pendente"
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 1200 ? 4 : (width >= 700 ? 2 : 1)
                columnSpacing: AppTheme.Theme.space12
                rowSpacing: AppTheme.Theme.space12

                MetricCard {
                    Layout.fillWidth: true
                    label: "Saves encontrados"
                    value: dashboard ? String(dashboard.slotCount) : "—"
                    detail: "slots no campo"
                    Text { objectName: "dashboardSlotCount"; visible: false; text: dashboard ? String(dashboard.slotCount) : "—" }
                }
                MetricCard { Layout.fillWidth: true; label: "Backups"; value: dashboard ? String(dashboard.backupCount) : "—"; detail: "registros protegidos" }
                MetricCard { Layout.fillWidth: true; label: "Último backup"; value: dashboard ? dashboard.lastBackupLabel : "Não disponível"; detail: "registro mais recente" }
                MetricCard { Layout.fillWidth: true; label: "Slot ativo"; value: dashboard ? dashboard.selectedSlotLabel : "Não disponível"; detail: "evidência exibida abaixo" }
            }

            AppCard {
                id: cropPanel
                objectName: "dashboardCropPanel"
                Layout.fillWidth: true
                implicitHeight: cropColumn.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: cropColumn
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space16
                    SectionHeader { Layout.fillWidth: true; title: "Evidência do cultivo"; subtitle: "Contagens reais do slot ativo" }
                    Item {
                        objectName: "dashboardNoSelectionState"
                        Layout.fillWidth: true
                        Layout.preferredHeight: emptyCopy.implicitHeight
                        visible: !dashboard || !dashboard.hasSelectedSlot
                        Text {
                            id: emptyCopy
                            width: parent.width
                            text: dashboard && dashboard.configurationState !== "valid" ? "Configure a origem dos saves para consultar o campo." : "Selecione um save para consultar a produção e a distribuição de crescimento."
                            color: AppTheme.Theme.textSecondary
                            font.family: AppTheme.Theme.bodyFont
                            font.pixelSize: AppTheme.Theme.typeBody
                            wrapMode: Text.WordWrap
                        }
                    }
                    AppButton {
                        visible: !dashboard || !dashboard.hasSelectedSlot
                        text: dashboard && dashboard.configurationState !== "valid" ? "Abrir configurações" : "Abrir saves"
                        tooltipText: text
                        onClicked: shell.navigate(dashboard && dashboard.configurationState !== "valid" ? 3 : 1)
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        visible: dashboard && dashboard.hasSelectedSlot
                        columns: width >= 1050 ? 4 : (width >= 620 ? 2 : 1)
                        columnSpacing: AppTheme.Theme.space20
                        rowSpacing: AppTheme.Theme.space4
                        InfoRow { Layout.fillWidth: true; label: "Registros"; value: dashboard ? String(dashboard.recordCount) : "—" }
                        InfoRow { Layout.fillWidth: true; label: "Plantados"; value: dashboard ? String(dashboard.plantedCount) : "—" }
                        InfoRow { Layout.fillWidth: true; label: "Regados"; value: dashboard ? String(dashboard.wateredCount) : "—" }
                        InfoRow { Layout.fillWidth: true; label: "Fertilizados"; value: dashboard ? String(dashboard.fertilizedCount) : "—" }
                        InfoRow { Layout.fillWidth: true; label: "Maduros"; value: dashboard ? String(dashboard.maturedCount) : "—" }
                        InfoRow { Layout.fillWidth: true; label: "Colhíveis"; value: dashboard ? String(dashboard.harvestableCount) : "—" }
                        InfoRow { Layout.fillWidth: true; label: "Mortos"; value: dashboard ? String(dashboard.deadCount) : "—" }
                    }
                }
            }

            AppCard {
                Layout.fillWidth: true
                visible: dashboard && dashboard.hasSelectedSlot && saves && saves.details && saves.details.hasCropProgress
                implicitHeight: growthColumn.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: growthColumn
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space12
                    SectionHeader { Layout.fillWidth: true; title: "Trilho de crescimento"; subtitle: "Estados encontrados, sem estimativas" }
                    Repeater {
                        model: saves && saves.details ? saves.details.growthStatesModel : null
                        delegate: ColumnLayout {
                            required property string label
                            required property int value
                            required property real ratio
                            Layout.fillWidth: true
                            spacing: AppTheme.Theme.space4
                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: label; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.bodyFont; font.pixelSize: AppTheme.Theme.typeBody; Layout.fillWidth: true }
                                Text { text: String(value); color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta }
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: AppTheme.Theme.space4
                                color: AppTheme.Theme.surfaceMuted
                                radius: height
                                Rectangle { width: parent.width * Math.max(0, Math.min(1, ratio)); height: parent.height; radius: height; color: AppTheme.Theme.accent }
                            }
                        }
                    }
                }
            }
        }
    }
}
