'use client'

import { useState, useRef, useEffect } from 'react'
import {
  Box,
  VStack,
  HStack,
  Input,
  Button,
  Text,
  Spinner,
  Badge,
  IconButton,
  Flex,
  Separator,
  Code,
  Accordion,
  Switch,
} from '@chakra-ui/react'
import dynamic from 'next/dynamic'
import { IoChatbubbleEllipsesOutline } from 'react-icons/io5'
import { HiOutlineRefresh } from 'react-icons/hi'
import { MdOutlineAccountTree } from 'react-icons/md'
import { chatAPI, ReasoningStep, ToolCall, ThreadInfo, AgentContext } from '@/lib/api'
import { toaster } from '@/components/ui/toaster'
import Sidebar from './Sidebar'

// Dynamically import MemoryGraphView to prevent SSR issues with vis-network
const MemoryGraphView = dynamic(() => import('./MemoryGraphView'), {
  ssr: false,
})

interface Message {
  id: string
  text: string
  sender: 'user' | 'agent'
  timestamp: Date
  reasoningSteps?: ReasoningStep[]
  agentContext?: AgentContext
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [memoryEnabled, setMemoryEnabled] = useState(false)
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [threads, setThreads] = useState<ThreadInfo[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activeThreadTitle, setActiveThreadTitle] = useState<string>('New Conversation')
  const [memoryGraphOpen, setMemoryGraphOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Check backend connection and load threads on mount
  useEffect(() => {
    checkConnection()
    loadThreads()
    loadLastActiveThread()
  }, [])

  // Load messages when active thread changes
  useEffect(() => {
    if (activeThreadId) {
      loadThreadMessages(activeThreadId)
    }
  }, [activeThreadId])

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const checkConnection = async () => {
    try {
      const healthy = await chatAPI.healthCheck()
      setIsConnected(healthy)
      if (!healthy) {
        toaster.create({
          title: 'Backend Disconnected',
          description: 'Unable to connect to the backend server',
          type: 'error',
          duration: 5000,
        })
      }
    } catch (error) {
      setIsConnected(false)
      toaster.create({
        title: 'Connection Error',
        description: 'Failed to connect to the backend',
        type: 'error',
        duration: 5000,
      })
    }
  }

  const loadThreads = async () => {
    try {
      const threadsList = await chatAPI.getThreads()
      setThreads(threadsList)
    } catch (error) {
      console.error('Failed to load threads:', error)
    }
  }

  const loadLastActiveThread = async () => {
    try {
      const lastThread = await chatAPI.getLastActiveThread()
      if (lastThread) {
        setActiveThreadId(lastThread.id)
        setActiveThreadTitle(lastThread.title)
      }
    } catch (error) {
      console.error('Failed to load last active thread:', error)
    }
  }

  const loadThreadMessages = async (threadId: string) => {
    try {
      const thread = await chatAPI.getThread(threadId)
      setActiveThreadTitle(thread.title)
      
      // Convert thread messages to Message format
      const loadedMessages: Message[] = thread.messages.map((msg) => ({
        id: msg.id,
        text: msg.text,
        sender: msg.sender,
        timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
        reasoningSteps: msg.reasoning_steps || undefined,
        agentContext: msg.agent_context || undefined,
      }))
      
      setMessages(loadedMessages)
    } catch (error) {
      console.error('Failed to load thread messages:', error)
      toaster.create({
        title: 'Load Failed',
        description: 'Failed to load conversation messages',
        type: 'error',
        duration: 5000,
      })
    }
  }

  const handleNewThread = () => {
    setActiveThreadId(null)
    setMessages([])
    setActiveThreadTitle('New Conversation')
    setSidebarOpen(false)
  }

  const handleSelectThread = (threadId: string) => {
    setActiveThreadId(threadId)
    setSidebarOpen(false)
  }

  const handleDeleteThread = (threadId: string) => {
    // If deleted thread is active, start a new thread
    if (threadId === activeThreadId) {
      handleNewThread()
    }
    // Refresh threads list
    loadThreads()
  }

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputValue,
      sender: 'user',
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    const messageText = inputValue
    setInputValue('')
    setIsLoading(true)

    try {
      const response = await chatAPI.sendMessage(messageText, memoryEnabled, activeThreadId)

      console.log('Chat API Response:', response)
      console.log('Reasoning steps:', response.reasoning_steps)
      console.log('Reasoning steps count:', response.reasoning_steps?.length || 0)
      console.log('Thread ID:', response.thread_id)

      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.response,
        sender: 'agent',
        timestamp: new Date(),
        reasoningSteps: response.reasoning_steps,
        agentContext: response.agent_context || undefined,
      }

      console.log('Agent message with reasoning steps:', agentMessage)
      console.log('Reasoning steps in message:', agentMessage.reasoningSteps)

      setMessages((prev) => [...prev, agentMessage])

      // Update active thread ID if it was newly created
      if (response.thread_id && !activeThreadId) {
        setActiveThreadId(response.thread_id)
      }

      // Refresh threads list to show updated title and message count
      loadThreads()
    } catch (error: any) {
      toaster.create({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to send message',
        type: 'error',
        duration: 5000,
      })

      // Add error message to chat
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: 'Sorry, I encountered an error processing your request. Please try again.',
        sender: 'agent',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleClearPreferences = async () => {
    try {
      setIsLoading(true)
      await chatAPI.clearPreferences()
      toaster.create({
        title: 'Preferences Cleared',
        description: 'All stored preferences have been cleared',
        type: 'success',
        duration: 3000,
      })
    } catch (error) {
      toaster.create({
        title: 'Clear Failed',
        description: 'Failed to clear preferences',
        type: 'error',
        duration: 5000,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const formatJSON = (obj: any): string => {
    try {
      return JSON.stringify(obj, null, 2)
    } catch {
      return String(obj)
    }
  }

  const renderToolCall = (toolCall: ToolCall, index: number) => {
    return (
      <Box key={index} mt={2} borderLeft="3px solid" borderColor="blue.400" pl={3}>
        <HStack mb={2}>
          <Badge colorPalette="blue" fontSize="xs">
            Tool Call
          </Badge>
          <Text fontWeight="bold" fontSize="sm">
            {toolCall.name}
          </Text>
        </HStack>
        
        <Box mb={2}>
          <Text fontSize="xs" color="gray.600" fontWeight="semibold" mb={1}>
            Arguments:
          </Text>
          <Code
            display="block"
            whiteSpace="pre-wrap"
            p={2}
            borderRadius="md"
            fontSize="xs"
            bg="gray.50"
            maxH="200px"
            overflowY="auto"
          >
            {formatJSON(toolCall.arguments)}
          </Code>
        </Box>
        
        <Box>
          <Text fontSize="xs" color="gray.600" fontWeight="semibold" mb={1}>
            Output:
          </Text>
          <Code
            display="block"
            whiteSpace="pre-wrap"
            p={2}
            borderRadius="md"
            fontSize="xs"
            bg="gray.50"
            maxH="300px"
            overflowY="auto"
          >
            {formatJSON(toolCall.output)}
          </Code>
        </Box>
      </Box>
    )
  }

  const renderAgentContext = (agentContext: AgentContext) => {
    return (
      <Box mb={3} pb={3} borderBottom="1px solid" borderColor="gray.200">
        <Accordion.Root collapsible defaultValue={[]}>
          <Accordion.Item value="agent-context" border="none">
            <Accordion.ItemTrigger px={0} py={2} _hover={{ bg: 'transparent' }}>
              <Box flex="1" textAlign="left">
                <HStack>
                  <Badge colorPalette="teal" fontSize="xs">
                    Agent Context
                  </Badge>
                  <Text fontSize="xs" color="gray.600">View system prompt and configuration</Text>
                </HStack>
              </Box>
              <Accordion.ItemIndicator />
            </Accordion.ItemTrigger>
            <Accordion.ItemContent>
              <Accordion.ItemBody px={0} pb={2}>
                <VStack align="stretch" gap={3}>
                  <Box
                    p={3}
                    bg="teal.50"
                    borderRadius="md"
                    border="1px solid"
                    borderColor="teal.200"
                  >
                    <VStack align="stretch" gap={3}>
                      {/* Model */}
                      <Box>
                        <Text fontSize="xs" color="gray.600" fontWeight="semibold" mb={1}>
                          Model:
                        </Text>
                        <Badge colorPalette="teal" fontSize="xs">
                          {agentContext.model}
                        </Badge>
                      </Box>
                      
                      {/* Memory Status */}
                      <Box>
                        <Text fontSize="xs" color="gray.600" fontWeight="semibold" mb={1}>
                          Memory:
                        </Text>
                        <Badge colorPalette={agentContext.memory_enabled ? 'green' : 'gray'} fontSize="xs">
                          {agentContext.memory_enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </Box>
                      
                      {/* Available Tools */}
                      <Box>
                        <Text fontSize="xs" color="gray.600" fontWeight="semibold" mb={1}>
                          Available Tools:
                        </Text>
                        <Flex gap={1} flexWrap="wrap">
                          {agentContext.available_tools.map((tool, idx) => (
                            <Badge key={idx} colorPalette="blue" fontSize="xs">
                              {tool}
                            </Badge>
                          ))}
                        </Flex>
                      </Box>
                      
                      {/* Preferences */}
                      {agentContext.preferences_applied && (
                        <Box>
                          <Text fontSize="xs" color="gray.600" fontWeight="semibold" mb={1}>
                            Active Preferences:
                          </Text>
                          <Code
                            display="block"
                            whiteSpace="pre-wrap"
                            p={2}
                            borderRadius="md"
                            fontSize="xs"
                            bg="white"
                            maxH="150px"
                            overflowY="auto"
                          >
                            {agentContext.preferences_applied}
                          </Code>
                        </Box>
                      )}
                      
                      {/* System Prompt */}
                      <Box>
                        <Text fontSize="xs" color="gray.600" fontWeight="semibold" mb={1}>
                          System Prompt:
                        </Text>
                        <Code
                          display="block"
                          whiteSpace="pre-wrap"
                          p={2}
                          borderRadius="md"
                          fontSize="xs"
                          bg="white"
                          maxH="300px"
                          overflowY="auto"
                        >
                          {agentContext.system_prompt}
                        </Code>
                      </Box>
                    </VStack>
                  </Box>
                </VStack>
              </Accordion.ItemBody>
            </Accordion.ItemContent>
          </Accordion.Item>
        </Accordion.Root>
      </Box>
    )
  }

  const renderReasoningSteps = (reasoningSteps: ReasoningStep[]) => {
    console.log('renderReasoningSteps called with:', reasoningSteps)
    console.log('reasoningSteps length:', reasoningSteps?.length || 0)
    
    if (!reasoningSteps || reasoningSteps.length === 0) {
      console.log('No reasoning steps to render')
      return null
    }

    console.log('Rendering reasoning steps:', reasoningSteps.length)

    return (
      <Box mb={3} pb={3} borderBottom="1px solid" borderColor="gray.200">
        <Accordion.Root collapsible defaultValue={[]}>
          <Accordion.Item value="reasoning-steps" border="none">
            <Accordion.ItemTrigger px={0} py={2} _hover={{ bg: 'transparent' }}>
              <Box flex="1" textAlign="left">
                <HStack>
                  <Badge colorPalette="purple" fontSize="xs">
                    Reasoning Steps ({reasoningSteps.length})
                  </Badge>
                  <Text fontSize="xs" color="gray.600">Click to view agent&apos;s thought process</Text>
                </HStack>
              </Box>
              <Accordion.ItemIndicator />
            </Accordion.ItemTrigger>
            <Accordion.ItemContent>
              <Accordion.ItemBody px={0} pb={2}>
                <VStack align="stretch" gap={3}>
                  {reasoningSteps.map((step, index) => (
                    <Box
                      key={index}
                      p={3}
                      bg="purple.50"
                      borderRadius="md"
                      border="1px solid"
                      borderColor="purple.200"
                    >
                      <HStack mb={2}>
                        <Badge colorPalette="purple" fontSize="xs">
                          Step {step.step_number}
                        </Badge>
                      </HStack>
                      
                      {step.reasoning && (
                        <Box mb={step.tool_calls.length > 0 ? 3 : 0}>
                          <Text fontSize="xs" color="gray.700" whiteSpace="pre-wrap">
                            {step.reasoning}
                          </Text>
                        </Box>
                      )}
                      
                      {step.tool_calls.length > 0 && (
                        <VStack align="stretch" gap={2}>
                          {step.tool_calls.map((toolCall, toolIndex) =>
                            renderToolCall(toolCall, toolIndex)
                          )}
                        </VStack>
                      )}
                    </Box>
                  ))}
                </VStack>
              </Accordion.ItemBody>
            </Accordion.ItemContent>
          </Accordion.Item>
        </Accordion.Root>
      </Box>
    )
  }

  const suggestedQueries = [
    'What are the latest news?',
    'Tell me about technology news',
    'What news do you have about climate change?',
    'Show me business news',
  ]

  return (
    <>
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onDeleteThread={handleDeleteThread}
        onThreadsUpdate={loadThreads}
      />

      <MemoryGraphView
        isOpen={memoryGraphOpen}
        onClose={() => setMemoryGraphOpen(false)}
      />

      <VStack gap={4} height="100%" width="100%">
        {/* Active Thread Title */}
        {activeThreadId && (
          <Box width="100%" px={4} pt={2}>
            <Text fontSize="xl" fontWeight="bold" color="gray.700">
              {activeThreadTitle}
            </Text>
          </Box>
        )}

        {/* Connection Status and Actions */}
        <HStack width="100%" justifyContent="space-between" px={4} flexWrap="wrap" gap={2}>
        <HStack>
          <Badge colorPalette={isConnected ? 'green' : 'red'}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </Badge>
          <IconButton
            aria-label="Refresh connection"
            size="sm"
            onClick={checkConnection}
            disabled={isLoading}
          >
            <HiOutlineRefresh />
          </IconButton>
        </HStack>
        
        <HStack gap={3}>
          <Flex gap={3} alignItems="center">
            <Switch.Root
              checked={memoryEnabled}
              onCheckedChange={({ checked }) => setMemoryEnabled(checked)}
              colorPalette="purple"
              disabled={!isConnected}
            >
              <Switch.HiddenInput />
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
              <Switch.Label fontSize="sm" fontWeight="medium">Memory</Switch.Label>
            </Switch.Root>
            <Badge 
              colorPalette={memoryEnabled ? 'purple' : 'gray'}
              fontSize="xs"
            >
              {memoryEnabled ? 'ON' : 'OFF'}
            </Badge>
          </Flex>
          
          <Button
            size="sm"
            colorPalette="purple"
            variant="outline"
            onClick={() => setMemoryGraphOpen(true)}
            disabled={!isConnected}
            leftIcon={<MdOutlineAccountTree />}
          >
            View Memory Graph
          </Button>
          
          <Button
            size="sm"
            colorPalette="red"
            variant="outline"
            onClick={handleClearPreferences}
            loading={isLoading}
            disabled={!isConnected}
          >
            Clear Preferences
          </Button>
        </HStack>
      </HStack>

      <Separator />

      {/* Chat Messages */}
      <Box
        flex={1}
        width="100%"
        overflowY="auto"
        bg="white"
        borderRadius="lg"
        boxShadow="md"
        p={6}
      >
        {messages.length === 0 ? (
          <VStack gap={6} height="100%" justifyContent="center">
            <IoChatbubbleEllipsesOutline size={48} color="var(--chakra-colors-blue-400)" />
            <Text fontSize="lg" color="gray.600" textAlign="center">
              Start a conversation by asking about world news!
            </Text>
            <VStack gap={2} width="100%">
              <Text fontSize="sm" color="gray.500" fontWeight="bold">
                Try asking:
              </Text>
              {suggestedQueries.map((query, index) => (
                <Button
                  key={index}
                  size="sm"
                  variant="outline"
                  colorPalette="blue"
                  onClick={() => setInputValue(query)}
                  width="80%"
                  disabled={!isConnected}
                >
                  {query}
                </Button>
              ))}
            </VStack>
          </VStack>
        ) : (
          <VStack gap={4} align="stretch">
            {messages.map((message) => (
              <Flex
                key={message.id}
                justifyContent={message.sender === 'user' ? 'flex-end' : 'flex-start'}
              >
                <Box
                  maxW="70%"
                  minW={message.sender === 'agent' && (message.agentContext || message.reasoningSteps) ? '60%' : 'auto'}
                  bg={message.sender === 'user' ? 'blue.500' : 'gray.100'}
                  color={message.sender === 'user' ? 'white' : 'black'}
                  px={4}
                  py={3}
                  borderRadius="lg"
                  boxShadow="sm"
                >
                  {message.sender === 'agent' && message.agentContext &&
                    renderAgentContext(message.agentContext)}

                  {message.sender === 'agent' && message.reasoningSteps &&
                    renderReasoningSteps(message.reasoningSteps)}

                  <Text
                    whiteSpace="pre-wrap"
                    mt={message.sender === 'agent' && (message.agentContext || message.reasoningSteps) ? 2 : 0}
                  >
                    {message.text}
                  </Text>
                  
                  <Text
                    fontSize="xs"
                    color={message.sender === 'user' ? 'blue.100' : 'gray.500'}
                    mt={1}
                  >
                    {message.timestamp.toLocaleTimeString()}
                  </Text>
                </Box>
              </Flex>
            ))}
            {isLoading && (
              <Flex justifyContent="flex-start">
                <Box bg="gray.100" px={4} py={3} borderRadius="lg">
                  <HStack>
                    <Spinner size="sm" />
                    <Text>Agent is thinking...</Text>
                  </HStack>
                </Box>
              </Flex>
            )}
            <div ref={messagesEndRef} />
          </VStack>
        )}
      </Box>

      {/* Input Area */}
      <HStack width="100%" gap={2}>
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask me about world news..."
          size="lg"
          bg="white"
          disabled={isLoading || !isConnected}
        />
        <Button
          colorPalette="blue"
          size="lg"
          onClick={sendMessage}
          loading={isLoading}
          disabled={!inputValue.trim() || !isConnected}
          px={8}
        >
          Send
        </Button>
      </HStack>
      </VStack>
    </>
  )
}
