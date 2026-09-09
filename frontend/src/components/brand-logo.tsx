import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

export function BrandLogo({
  compact = false,
  inverse = false,
}: {
  compact?: boolean;
  inverse?: boolean;
}) {
  const theme = useTheme();
  const symbol = inverse || theme.palette.mode === "dark"
    ? "/assets/brand/talento-symbol-white.svg"
    : "/assets/brand/talento-symbol-blue.svg";

  return (
    <Stack direction="row" alignItems="center" spacing={1.25} sx={{ minWidth: 0 }}>
      <Box component="img" src={symbol} alt="" aria-hidden sx={{ width: 34, height: 34, flexShrink: 0 }} />
      {!compact && (
        <Typography
          component="span"
          sx={{
            color: inverse ? "common.white" : "text.primary",
            fontSize: 23,
            fontWeight: 800,
            letterSpacing: -0.7,
          }}
        >
          talento
        </Typography>
      )}
    </Stack>
  );
}
