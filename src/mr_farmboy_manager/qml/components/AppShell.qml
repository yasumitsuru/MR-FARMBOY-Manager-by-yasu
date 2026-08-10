import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as AppTheme
import "../pages"

Item {
    id: shell
    property var controller
    property int currentIndex: 0
    readonly property bool wideNavigation: width >= 1200
    readonly property bool railNavigation: width >= 1000 && width < 1200
    readonly property bool drawerNavigation: width < 1000
    readonly property var pageTitles: ["Visão do cultivo", "Saves", "Backups", "Configurações", "Diagnósticos"]
    readonly property var pageSymbols: ["◉", "▤", "▣", "⚙", "⌁"]

    function navigate(index) {
        currentIndex = index
        drawer.close()
    }

    Rectangle { anchors.fill: parent; color: AppTheme.Theme.background }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            id: sidebar
            Layout.fillHeight: true
            Layout.preferredWidth: shell.wideNavigation ? 232 : 80
            visible: !shell.drawerNavigation
            color: AppTheme.Theme.sidebar
            Behavior on Layout.preferredWidth { NumberAnimation { duration: AppTheme.Theme.motionSlow } }
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: AppTheme.Theme.space16
                spacing: AppTheme.Theme.space12
                Text { text: shell.wideNavigation ? "MR FARMBOY" : "MR"; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.displayFont; font.pixelSize: shell.wideNavigation ? AppTheme.Theme.typeCardTitle : AppTheme.Theme.typeBody; font.weight: AppTheme.Theme.weightBold; Layout.fillWidth: true; horizontalAlignment: shell.wideNavigation ? Text.AlignLeft : Text.AlignHCenter }
                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: AppTheme.Theme.borderWidth; color: AppTheme.Theme.border }
                SidebarItem { objectName: "navDashboard"; Layout.fillWidth: true; compact: shell.railNavigation; label: shell.pageTitles[0]; symbol: shell.pageSymbols[0]; selected: shell.currentIndex === 0; onActivated: shell.navigate(0) }
                SidebarItem { objectName: "navSaves"; Layout.fillWidth: true; compact: shell.railNavigation; label: shell.pageTitles[1]; symbol: shell.pageSymbols[1]; selected: shell.currentIndex === 1; onActivated: shell.navigate(1) }
                SidebarItem { objectName: "navBackups"; Layout.fillWidth: true; compact: shell.railNavigation; label: shell.pageTitles[2]; symbol: shell.pageSymbols[2]; selected: shell.currentIndex === 2; onActivated: shell.navigate(2) }
                SidebarItem { objectName: "navSettings"; Layout.fillWidth: true; compact: shell.railNavigation; label: shell.pageTitles[3]; symbol: shell.pageSymbols[3]; selected: shell.currentIndex === 3; onActivated: shell.navigate(3) }
                SidebarItem { objectName: "navDiagnostics"; Layout.fillWidth: true; compact: shell.railNavigation; label: shell.pageTitles[4]; symbol: shell.pageSymbols[4]; selected: shell.currentIndex === 4; onActivated: shell.navigate(4) }
                Item { Layout.fillHeight: true }
                StatusBadge { Layout.fillWidth: true; status: shell.controller && shell.controller.busy ? "warning" : "success"; label: shell.controller && shell.controller.busy ? "Atualizando" : "Pronto" }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: AppTheme.Theme.sidebar
                border.width: AppTheme.Theme.borderWidth
                border.color: AppTheme.Theme.border
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: AppTheme.Theme.space16
                    spacing: AppTheme.Theme.space12
                    AppButton { objectName: "navMenuButton"; visible: shell.drawerNavigation; text: "Menu"; tooltipText: "Abrir navegação"; onClicked: drawer.open() }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: AppTheme.Theme.space4
                        Text {
                            text: shell.pageTitles[shell.currentIndex]
                            color: AppTheme.Theme.textPrimary
                            font.family: AppTheme.Theme.displayFont
                            font.pixelSize: AppTheme.Theme.typePageTitle
                            font.weight: AppTheme.Theme.weightBold
                        }
                        Text {
                            text: "Contexto do save e ações seguras"
                            color: AppTheme.Theme.textSecondary
                            font.family: AppTheme.Theme.bodyFont
                            font.pixelSize: AppTheme.Theme.typeMeta
                        }
                    }
                    Text { objectName: "lastUpdatedLabel"; text: shell.controller && shell.controller.dashboard ? shell.controller.dashboard.lastUpdatedLabel : "Não disponível"; color: AppTheme.Theme.textMuted; font.family: AppTheme.Theme.utilityFont; font.pixelSize: AppTheme.Theme.typeMeta; visible: shell.width >= 1200 }
                }
            }
            StackLayout {
                id: pageStack
                objectName: "pageStack"
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: shell.currentIndex
                DashboardPage { controller: shell.controller; shell: shell }
                SavesPage { controller: shell.controller; shell: shell }
                Item { Accessible.name: shell.pageTitles[2] }
                Item { Accessible.name: shell.pageTitles[3] }
                Item { Accessible.name: shell.pageTitles[4] }
            }
        }
    }

    Drawer {
        id: drawer
        edge: Qt.LeftEdge
        width: Math.min(280, shell.width - AppTheme.Theme.space32)
        height: shell.height
        modal: false
        interactive: shell.drawerNavigation
        background: Rectangle { color: AppTheme.Theme.sidebar; border.width: AppTheme.Theme.borderWidth; border.color: AppTheme.Theme.border }
        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: AppTheme.Theme.space16
            spacing: AppTheme.Theme.space12
            Text { text: "MR FARMBOY"; color: AppTheme.Theme.textPrimary; font.family: AppTheme.Theme.displayFont; font.pixelSize: AppTheme.Theme.typeCardTitle; font.weight: AppTheme.Theme.weightBold }
            Repeater { model: 5; SidebarItem { Layout.fillWidth: true; label: shell.pageTitles[index]; symbol: shell.pageSymbols[index]; selected: shell.currentIndex === index; onActivated: shell.navigate(index) } }
        }
        enter: Transition { NumberAnimation { property: "x"; duration: AppTheme.Theme.motionSlow } }
        exit: Transition { NumberAnimation { property: "x"; duration: AppTheme.Theme.motionSlow } }
    }
}
