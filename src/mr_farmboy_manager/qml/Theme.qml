pragma Singleton
import QtQuick

QtObject {
    // Dark-first palette.
    readonly property color background: "#0B1410"
    readonly property color sidebar: "#0F1C16"
    readonly property color surface: "#14231C"
    readonly property color surfaceRaised: "#1A2D24"
    readonly property color surfaceMuted: "#20362B"
    readonly property color accent: "#86C96F"
    readonly property color accentStrong: "#63AD56"
    readonly property color success: "#59C58B"
    readonly property color warning: "#E5B95C"
    readonly property color error: "#ED776D"
    readonly property color textPrimary: "#F2F6F3"
    readonly property color textSecondary: "#A9BBB0"
    readonly property color textMuted: "#74877C"
    readonly property color border: "#294337"
    readonly property color focus: accent
    readonly property color disabled: textMuted
    readonly property color transparent: "transparent"

    // Reserved equivalents keep the theme API stable for a future light mode.
    readonly property color lightBackground: "#F2F6F3"
    readonly property color lightSurface: "#FFFFFF"
    readonly property color lightTextPrimary: "#14231C"

    readonly property int space4: 4
    readonly property int space8: 8
    readonly property int space12: 12
    readonly property int space16: 16
    readonly property int space20: 20
    readonly property int space24: 24
    readonly property int space32: 32
    readonly property int space40: 40
    readonly property int radiusControl: 8
    readonly property int radiusCard: 12
    readonly property int radiusPanel: 16
    readonly property int borderWidth: 1
    readonly property int controlHeight: 36
    readonly property int primaryActionHeight: 40

    readonly property string displayFont: "Segoe UI Variable Display"
    readonly property string bodyFont: "Segoe UI"
    readonly property string utilityFont: "Cascadia Mono"
    readonly property int weightRegular: Font.Normal
    readonly property int weightSemibold: Font.DemiBold
    readonly property int weightBold: Font.Bold
    readonly property int typeMeta: 12
    readonly property int typeBody: 14
    readonly property int typeCardTitle: 16
    readonly property int typePageTitle: 22
    readonly property int typeMetric: 28

    readonly property int motionFast: 120
    readonly property int motionStandard: 160
    readonly property int motionSlow: 180
}
