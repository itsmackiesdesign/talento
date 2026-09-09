import { alpha, createTheme, responsiveFontSizes, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type ColorMode = "light" | "dark";

interface ColorModeContextValue {
  mode: ColorMode;
  toggleMode: () => void;
}

const ColorModeContext = createContext<ColorModeContextValue | null>(null);

const GREY = {
  0: "#FFFFFF",
  100: "#F9FAFB",
  200: "#F4F6F8",
  300: "#DFE3E8",
  400: "#C4CDD5",
  500: "#919EAB",
  600: "#637381",
  700: "#454F5B",
  800: "#212B36",
  900: "#161C24",
} as const;

const BRAND = {
  lighter: "#E8E7FF",
  light: "#7774FF",
  main: "#2F2BFF",
  dark: "#211DD9",
  darker: "#15118F",
  contrastText: "#FFFFFF",
} as const;

const DARK = {
  default: "#050507",
  paper: "#111116",
} as const;

function buildTheme(mode: ColorMode) {
  const isLight = mode === "light";
  const base = createTheme({
    palette: {
      mode,
      primary: BRAND,
      secondary: {
        light: "#B49BFF",
        main: "#7A5AF8",
        dark: "#5E3EC8",
        contrastText: "#FFFFFF",
      },
      info: {
        light: "#61F3F3",
        main: "#00B8D9",
        dark: "#006C9C",
        contrastText: "#FFFFFF",
      },
      success: {
        light: "#77ED8B",
        main: "#22C55E",
        dark: "#118D57",
        contrastText: "#FFFFFF",
      },
      warning: {
        light: "#FFD666",
        main: "#FFAB00",
        dark: "#B76E00",
        contrastText: GREY[800],
      },
      error: {
        light: "#FFAC82",
        main: "#FF5630",
        dark: "#B71D18",
        contrastText: "#FFFFFF",
      },
      grey: GREY,
      divider: alpha(GREY[500], 0.2),
      text: isLight
        ? { primary: GREY[800], secondary: GREY[600], disabled: GREY[500] }
        : { primary: GREY[0], secondary: GREY[500], disabled: GREY[600] },
      background: isLight
        ? { default: GREY[100], paper: GREY[0] }
        : { default: DARK.default, paper: DARK.paper },
      action: {
        active: isLight ? GREY[600] : GREY[500],
        hover: alpha(GREY[500], 0.08),
        selected: alpha(GREY[500], 0.16),
        disabled: alpha(GREY[500], 0.8),
        disabledBackground: alpha(GREY[500], 0.24),
        focus: alpha(GREY[500], 0.24),
      },
    },
    shape: { borderRadius: 8 },
    typography: {
      fontFamily: '"Public Sans", Arial, sans-serif',
      fontWeightRegular: 400,
      fontWeightMedium: 500,
      fontWeightBold: 700,
      h1: { fontWeight: 800, fontSize: "2.5rem", lineHeight: 1.2 },
      h2: { fontWeight: 800, fontSize: "2rem", lineHeight: 1.25 },
      h3: { fontWeight: 700, fontSize: "1.75rem", lineHeight: 1.35 },
      h4: { fontWeight: 700, fontSize: "1.5rem", lineHeight: 1.4 },
      h5: { fontWeight: 700, fontSize: "1.25rem", lineHeight: 1.5 },
      h6: { fontWeight: 700, fontSize: "1.125rem", lineHeight: 1.55 },
      subtitle1: { fontWeight: 600, fontSize: "1rem", lineHeight: 1.5 },
      subtitle2: { fontWeight: 600, fontSize: "0.875rem", lineHeight: 1.55 },
      body1: { fontSize: "1rem", lineHeight: 1.5 },
      body2: { fontSize: "0.875rem", lineHeight: 1.55 },
      caption: { fontSize: "0.75rem", lineHeight: 1.5 },
      overline: { fontWeight: 700, fontSize: "0.75rem", lineHeight: 1.5, letterSpacing: 1.1 },
      button: { fontWeight: 700, fontSize: "0.875rem", textTransform: "none" },
    },
  });

  const cardShadow = isLight
    ? `0 0 2px 0 ${alpha(GREY[500], 0.2)}, 0 12px 24px -4px ${alpha(GREY[500], 0.12)}`
    : `0 0 2px 0 ${alpha("#000000", 0.24)}, 0 12px 24px -4px ${alpha("#000000", 0.24)}`;

  base.components = {
    MuiCssBaseline: {
      styleOverrides: {
        "*": { boxSizing: "border-box" },
        html: { width: "100%", minHeight: "100%", WebkitOverflowScrolling: "touch" },
        body: {
          width: "100%",
          minHeight: "100%",
          margin: 0,
          backgroundColor: base.palette.background.default,
        },
        "#root": { width: "100%", minHeight: "100%" },
        "::selection": { color: "#FFFFFF", backgroundColor: BRAND.main },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { minHeight: 44, borderRadius: 8, paddingInline: 14 },
        sizeLarge: { minHeight: 48, paddingInline: 20, fontSize: 15 },
        sizeSmall: { minHeight: 44, paddingInline: 10, fontSize: 13 },
        containedPrimary: {
          boxShadow: `0 8px 16px ${alpha(BRAND.main, 0.24)}`,
          "&:hover": { boxShadow: `0 8px 20px ${alpha(BRAND.main, 0.34)}` },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { width: 44, height: 44, borderRadius: 10 },
        sizeSmall: { width: 44, height: 44 },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: { position: "relative", borderRadius: 16, boxShadow: cardShadow, backgroundImage: "none" },
      },
    },
    MuiCardHeader: {
      styleOverrides: { root: { padding: 24, paddingBottom: 0 } },
      defaultProps: { titleTypographyProps: { variant: "h6" }, subheaderTypographyProps: { variant: "body2" } },
    },
    MuiCardContent: {
      styleOverrides: { root: { padding: 24, "&:last-child": { paddingBottom: 24 } } },
    },
    MuiPaper: {
      styleOverrides: { rounded: { borderRadius: 16 } },
    },
    MuiTextField: {
      defaultProps: { variant: "outlined" },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          "& .MuiOutlinedInput-notchedOutline": { borderColor: alpha(GREY[500], 0.24) },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: GREY[500] },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: BRAND.main, borderWidth: 2 },
        },
        input: { paddingTop: 14, paddingBottom: 14 },
      },
    },
    MuiInputLabel: {
      styleOverrides: { root: { fontWeight: 500 } },
    },
    MuiMenu: {
      styleOverrides: { paper: { marginTop: 8, padding: 4, boxShadow: cardShadow } },
    },
    MuiMenuItem: {
      styleOverrides: { root: { minHeight: 40, marginBottom: 2, borderRadius: 6, fontSize: 14 } },
    },
    MuiPopover: {
      styleOverrides: { paper: { boxShadow: cardShadow } },
    },
    MuiDialog: {
      styleOverrides: { paper: { borderRadius: 16, boxShadow: cardShadow } },
    },
    MuiDrawer: {
      styleOverrides: { paper: { backgroundImage: "none" } },
    },
    MuiTooltip: {
      defaultProps: { arrow: true },
      styleOverrides: { tooltip: { borderRadius: 8, fontSize: 12 }, arrow: { color: GREY[800] } },
    },
    MuiChip: {
      styleOverrides: { root: { borderRadius: 8, fontWeight: 600 }, sizeSmall: { height: 26 } },
    },
    MuiTabs: {
      styleOverrides: { indicator: { height: 3, borderRadius: 3 } },
    },
    MuiTab: {
      styleOverrides: { root: { minHeight: 48, fontWeight: 600, textTransform: "none" } },
    },
    MuiTableCell: {
      styleOverrides: {
        head: { color: base.palette.text.secondary, fontWeight: 600, backgroundColor: alpha(GREY[500], 0.08) },
        root: { borderBottom: `1px dashed ${base.palette.divider}` },
      },
    },
    MuiSwitch: {
      styleOverrides: { root: { padding: 8 } },
    },
  };

  return responsiveFontSizes(base);
}

export function AppThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ColorMode>(() => {
    const saved = localStorage.getItem("talento-theme");
    return saved === "dark" ? "dark" : "light";
  });

  useEffect(() => {
    localStorage.setItem("talento-theme", mode);
    document.documentElement.classList.toggle("dark", mode === "dark");
    document.documentElement.style.colorScheme = mode;
  }, [mode]);

  const value = useMemo<ColorModeContextValue>(
    () => ({ mode, toggleMode: () => setMode((current) => (current === "light" ? "dark" : "light")) }),
    [mode],
  );
  const theme = useMemo(() => buildTheme(mode), [mode]);

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export function useColorMode() {
  const value = useContext(ColorModeContext);
  if (!value) throw new Error("useColorMode must be used inside AppThemeProvider");
  return value;
}
