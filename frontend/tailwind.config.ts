import type { Config } from "tailwindcss";
import defaultTheme from "tailwindcss/defaultTheme";

const token = (name: string) => `hsl(var(--${name}) / <alpha-value>)`;

export default {
	darkMode: ["class"],
	content: ["./src/**/*.{ts,tsx}"],
	prefix: "",
	theme: {
		container: {
			center: true,
			padding: "2rem",
			screens: { "2xl": "1400px" },
		},
		extend: {
			fontFamily: {
				sans: ["Inter Variable", ...defaultTheme.fontFamily.sans],
				mono: ["JetBrains Mono", ...defaultTheme.fontFamily.mono],
			},
			fontSize: {
				"2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
			},
			colors: {
				border: token("border"),
				input: token("input"),
				ring: token("ring"),
				background: token("background"),
				foreground: token("foreground"),
				surface: {
					1: token("card"),
					2: token("surface-2"),
					3: token("surface-3"),
				},
				primary: { DEFAULT: token("primary"), foreground: token("primary-foreground") },
				secondary: { DEFAULT: token("secondary"), foreground: token("secondary-foreground") },
				destructive: { DEFAULT: token("destructive"), foreground: token("destructive-foreground") },
				muted: { DEFAULT: token("muted"), foreground: token("muted-foreground") },
				accent: { DEFAULT: token("accent"), foreground: token("accent-foreground") },
				popover: { DEFAULT: token("popover"), foreground: token("popover-foreground") },
				card: { DEFAULT: token("card"), foreground: token("card-foreground") },
				success: token("success"),
				warning: token("warning"),
				danger: token("danger"),
				info: token("info"),
				// Legacy ant-sim palette (pages removed in step 14).
				simulation: {
					"ant-rule": "hsl(var(--ant-rule-based))",
					"ant-llm": "hsl(var(--ant-llm))",
					"ant-hybrid": "hsl(var(--ant-hybrid))",
					food: "hsl(var(--food-color))",
					"grid-cell": "hsl(var(--grid-cell))",
					"grid-border": "hsl(var(--grid-border))",
				},
			},
			opacity: { 12: "0.12", 8: "0.08" },
			borderRadius: {
				xl: "calc(var(--radius) + 4px)",
				lg: "var(--radius)",
				md: "calc(var(--radius) - 2px)",
				sm: "calc(var(--radius) - 4px)",
			},
			boxShadow: {
				e1: "0 1px 2px 0 hsl(var(--shadow-color) / 0.12)",
				e2: "0 4px 12px -2px hsl(var(--shadow-color) / 0.18), 0 1px 3px 0 hsl(var(--shadow-color) / 0.10)",
				e3: "0 16px 40px -8px hsl(var(--shadow-color) / 0.35), 0 2px 6px 0 hsl(var(--shadow-color) / 0.14)",
			},
			transitionTimingFunction: {
				smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
				"out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
			},
			transitionDuration: {
				fast: "120ms",
				base: "180ms",
				slow: "260ms",
			},
			keyframes: {
				"accordion-down": {
					from: { height: "0" },
					to: { height: "var(--radix-accordion-content-height)" },
				},
				"accordion-up": {
					from: { height: "var(--radix-accordion-content-height)" },
					to: { height: "0" },
				},
				shimmer: {
					from: { backgroundPosition: "200% 0" },
					to: { backgroundPosition: "-200% 0" },
				},
			},
			animation: {
				"accordion-down": "accordion-down 0.2s ease-out",
				"accordion-up": "accordion-up 0.2s ease-out",
				shimmer: "shimmer 1.8s linear infinite",
			},
		},
	},
	plugins: [require("tailwindcss-animate")],
} satisfies Config;
