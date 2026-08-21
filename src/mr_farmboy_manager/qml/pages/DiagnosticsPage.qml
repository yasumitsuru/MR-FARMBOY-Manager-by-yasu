import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import ".." as AppTheme

Item {
    id: page
    objectName: "diagnosticsPage"
    property var controller
    property var diagnostics: controller ? controller.diagnostics : null
    property var shell
    readonly property bool narrowLayout: width < 700
    readonly property bool hasDiagnosticEvents: diagnostics && diagnostics.events.length > 0
    readonly property string diagnosticText: hasDiagnosticEvents ? diagnostics.events : "Nenhum evento de diagnóstico disponível."

    ScrollView {
        id: diagnosticsScroll
        objectName: "diagnosticsScrollView"
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: diagnosticsScroll.availableWidth - AppTheme.Theme.space24 * 2
            x: AppTheme.Theme.space24
            spacing: AppTheme.Theme.space20

            AppCard {
                Layout.fillWidth: true
                implicitHeight: sourceContent.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: sourceContent
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space8
                    SectionHeader { Layout.fillWidth: true; title: "Diagnósticos"; subtitle: "Trecho limitado do log local para suporte" }
                    TextEdit { Layout.fillWidth: true; readOnly: true; text: diagnostics ? diagnostics.logPathLabel : "Não disponível"; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.utilityFont; wrapMode: TextEdit.WrapAnywhere; selectByMouse: true }
                    TextEdit { Layout.fillWidth: true; readOnly: true; text: diagnostics ? diagnostics.logDirectoryLabel : "Não disponível"; color: AppTheme.Theme.textSecondary; font.family: AppTheme.Theme.utilityFont; wrapMode: TextEdit.WrapAnywhere; selectByMouse: true }
                }
            }

            AppCard {
                Layout.fillWidth: true
                implicitHeight: eventsContent.implicitHeight + AppTheme.Theme.space32
                ColumnLayout {
                    id: eventsContent
                    anchors.fill: parent
                    spacing: AppTheme.Theme.space12
                    SectionHeader { Layout.fillWidth: true; title: "Eventos recentes"; subtitle: "Até 50 linhas; o texto pode ser selecionado e copiado" }
                    TextEdit {
                        objectName: "diagnosticsEvents"
                        property bool wrapsText: true
                        Layout.fillWidth: true
                        text: page.diagnosticText
                        color: AppTheme.Theme.textPrimary
                        font.family: AppTheme.Theme.utilityFont
                        font.pixelSize: AppTheme.Theme.typeMeta
                        wrapMode: TextEdit.WrapAnywhere
                        selectByMouse: true
                    }
                    Text { objectName: "diagnosticsStatus"; Layout.fillWidth: true; visible: diagnostics && diagnostics.statusMessage.length > 0; text: diagnostics ? diagnostics.statusMessage : ""; color: page.hasDiagnosticEvents ? AppTheme.Theme.success : AppTheme.Theme.error; font.family: AppTheme.Theme.bodyFont; wrapMode: Text.WordWrap }
                    RowLayout {
                        Layout.fillWidth: true
                        AppButton { objectName: "copyDiagnosticButton"; text: "Copiar diagnóstico"; onClicked: if (diagnostics) diagnostics.copyDiagnostic() }
                        AppButton { objectName: "openLogsButton"; text: "Abrir pasta de logs"; onClicked: if (diagnostics) diagnostics.openLogDirectory() }
                        Item { Layout.fillWidth: true }
                    }
                }
            }
        }
    }
}
