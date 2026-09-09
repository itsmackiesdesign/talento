import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

export function TalentoMark({
  color = "currentColor",
  size = 34,
}: {
  color?: string;
  size?: number | string;
}) {
  return (
    <Box
      component="svg"
      viewBox="0 0 540 535"
      aria-hidden
      focusable="false"
      sx={{ display: "block", width: size, height: size, flexShrink: 0, overflow: "visible", color }}
    >
      <path fill="currentColor" d="M0 535A270 270 0 0 1 540 535H420A150 150 0 0 0 120 535Z" />
      <circle fill="currentColor" cx="270" cy="88" r="88" />
    </Box>
  );
}

export function BrandLogo({
  compact = false,
  inverse = false,
}: {
  compact?: boolean;
  inverse?: boolean;
}) {
  const theme = useTheme();
  const wordColor = inverse ? theme.palette.common.white : theme.palette.text.primary;
  const markColor = inverse ? theme.palette.common.white : theme.palette.primary.main;

  return (
    <Stack
      direction="row"
      alignItems="flex-end"
      spacing={compact ? 0 : 0.1}
      role="img"
      aria-label="talento"
      sx={{ minWidth: 0, width: "fit-content" }}
    >
      {!compact && (
        <Typography
          component="span"
          aria-hidden
          sx={{
            color: wordColor,
            fontSize: 23,
            fontWeight: 800,
            lineHeight: 1,
            letterSpacing: -1.2,
          }}
        >
          talent
        </Typography>
      )}
      <TalentoMark color={markColor} size={compact ? 32 : "0.83em"} />
    </Stack>
  );
}
