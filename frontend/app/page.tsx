'use client'

import { Box, Heading, Flex } from '@chakra-ui/react'
import ChatInterface from '@/components/ChatInterface'

export default function Home() {
  return (
    <Flex direction="column" height="100vh" width="100vw" overflow="hidden">
      <Box
        bg="blue.600"
        color="white"
        py={4}
        px={6}
        boxShadow="md"
      >
        <Heading size="xl" textAlign="center">
          News Chat Agent
        </Heading>
      </Box>
      
      <Flex flex={1} overflow="hidden" position="relative">
        <Box
          flex={1}
          height="100%"
          overflow="hidden"
          px={{ base: 4, md: 8 }}
          py={4}
        >
          <ChatInterface />
        </Box>
      </Flex>
    </Flex>
  )
}
