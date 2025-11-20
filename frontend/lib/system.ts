import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react"

const config = defineConfig({
  globalCss: {
    "body": {
      bg: "gray.50",
    },
  },
})

export const system = createSystem(defaultConfig, config)


