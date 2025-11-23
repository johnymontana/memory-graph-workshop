'use client'

import { useEffect, useState, useMemo } from 'react'
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Spinner,
  Badge,
  IconButton,
} from '@chakra-ui/react'
import { HiX, HiRefresh } from 'react-icons/hi'
import dynamic from 'next/dynamic'
import { chatAPI, MemoryGraph, GraphNode } from '@/lib/api'

// Define types for NVL
interface NvlNode {
  id: string
  caption?: string
  size?: number
  color?: string
  selected?: boolean
  data?: any
}

interface NvlRelationship {
  id: string
  from: string
  to: string
  caption?: string
  selected?: boolean
}

interface MouseEventCallbacks {
  onNodeClick?: (node: NvlNode) => void
  onRelationshipClick?: (rel: NvlRelationship) => void
}

// Dynamically import NVL to avoid SSR issues
const InteractiveNvlWrapper = dynamic(
  () => import('@neo4j-nvl/react').then((mod) => mod.InteractiveNvlWrapper),
  { 
    ssr: false,
    loading: () => (
      <VStack height="100%" justifyContent="center" gap={4}>
        <Spinner size="xl" />
        <Text color="gray.600">Loading graph visualization...</Text>
      </VStack>
    ),
  }
)

interface MemoryGraphViewProps {
  isOpen: boolean
  onClose: () => void
}

// Memory type classification
type MemoryType = 'short-term' | 'user-profile' | 'procedural'

interface MemoryTypeFilters {
  'short-term': boolean
  'user-profile': boolean
  'procedural': boolean
}

export default function MemoryGraphView({ isOpen, onClose }: MemoryGraphViewProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [graphData, setGraphData] = useState<MemoryGraph | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [selectedRelationship, setSelectedRelationship] = useState<{
    id: string
    from: string
    to: string
    type: string
    properties: Record<string, any>
  } | null>(null)
  
  // Memory type filters - all enabled by default
  const [memoryFilters, setMemoryFilters] = useState<MemoryTypeFilters>({
    'short-term': true,
    'user-profile': true,
    'procedural': true,
  })

  const loadGraphData = async () => {
    setIsLoading(true)
    setError(null)
    setSelectedNode(null)
    setSelectedRelationship(null)
    try {
      const data = await chatAPI.getMemoryGraph()
      setGraphData(data)
      
      if (data.nodes.length === 0) {
        setError('No memory data available. Enable memory and chat to build your memory graph.')
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to load memory graph'
      setError(errorMsg)
    } finally {
      setIsLoading(false)
    }
  }

  // Calculate graph statistics
  const graphStats = useMemo(() => {
    if (!graphData) return { nodes: {}, relationships: {} }
    
    const nodeStats = graphData.nodes.reduce((acc, node) => {
      node.labels.forEach(label => {
        acc[label] = (acc[label] || 0) + 1
      })
      return acc
    }, {} as Record<string, number>)
    
    const relStats = graphData.relationships.reduce((acc, rel) => {
      acc[rel.type] = (acc[rel.type] || 0) + 1
      return acc
    }, {} as Record<string, number>)
    
    return { nodes: nodeStats, relationships: relStats }
  }, [graphData])

  // Helper function to get node label (primary label)
  const getNodeLabel = (node: GraphNode): string => {
    if (node.labels.includes('Thread')) return 'Thread'
    if (node.labels.includes('Message')) return 'Message'
    if (node.labels.includes('ReasoningStep')) return 'ReasoningStep'
    if (node.labels.includes('ToolCall')) return 'ToolCall'
    if (node.labels.includes('Tool')) return 'Tool'
    if (node.labels.includes('UserPreference')) return 'UserPreference'
    if (node.labels.includes('PreferenceCategory')) return 'PreferenceCategory'
    if (node.labels.includes('Location')) return 'Location'
    if (node.labels.includes('Person')) return 'Person'
    if (node.labels.includes('Organization')) return 'Organization'
    if (node.labels.includes('Topic')) return 'Topic'
    return node.labels[0] || 'Unknown'
  }

  // Helper function to classify node by memory type
  const getNodeMemoryType = (node: GraphNode): MemoryType => {
    const nodeType = getNodeLabel(node)
    
    // Short-term memory: conversations and messages
    if (nodeType === 'Thread' || nodeType === 'Message') {
      return 'short-term'
    }
    
    // User profile memory: preferences, categories, and entities
    if (nodeType === 'UserPreference' || nodeType === 'PreferenceCategory' ||
        nodeType === 'Location' || nodeType === 'Person' || 
        nodeType === 'Organization' || nodeType === 'Topic') {
      return 'user-profile'
    }
    
    // Procedural memory: reasoning, tool calls, and tools
    if (nodeType === 'ReasoningStep' || nodeType === 'ToolCall' || nodeType === 'Tool') {
      return 'procedural'
    }
    
    return 'short-term' // Default fallback
  }

  // Memory type colors for backgrounds/grouping
  const MEMORY_TYPE_COLORS = {
    'short-term': {
      bg: 'rgba(76, 142, 218, 0.08)',     // Light blue
      border: '#4C8EDA',
      label: 'Short-Term Memory',
      description: 'Conversations & Messages'
    },
    'user-profile': {
      bg: 'rgba(255, 196, 84, 0.08)',     // Light yellow/gold
      border: '#FFC454',
      label: 'User Profile Memory',
      description: 'Preferences, Categories & Entities'
    },
    'procedural': {
      bg: 'rgba(141, 204, 147, 0.08)',    // Light green
      border: '#8DCC93',
      label: 'Procedural Memory',
      description: 'Reasoning, Tools & Actions'
    }
  }

  // Node type colors - using Neo4j Bloom/NVL default color palette
  const NODE_COLORS = {
    Thread: '#4C8EDA',           // Blue - conversation threads (primary entry points)
    Message: '#57C7E3',          // Cyan - individual messages
    ReasoningStep: '#8DCC93',    // Green - reasoning process
    ToolCall: '#F79767',         // Orange - tool executions
    Tool: '#C990C0',             // Purple - canonical tools
    UserPreference: '#FFC454',   // Yellow/Gold - user preferences (NVL default)
    PreferenceCategory: '#DA7194', // Pink - preference categories
    Location: '#68BDF6',         // Light blue - locations
    Person: '#DE9BF9',           // Light purple - people
    Organization: '#FB95AF',     // Light pink - organizations
    Topic: '#A4DD00',            // Lime green - topics
  }

  // Helper function to format property values (especially dates)
  const formatPropertyValue = (value: any): string => {
    if (value === null || value === undefined) {
      return 'null'
    }
    
    // Handle Neo4j DateTime objects (they come as objects with year, month, day, etc.)
    if (typeof value === 'object' && value !== null) {
      // Check if it's a Neo4j DateTime object
      if ('year' in value && 'month' in value && 'day' in value) {
        try {
          const year = value.year?.low ?? value.year
          const month = String(value.month?.low ?? value.month).padStart(2, '0')
          const day = String(value.day?.low ?? value.day).padStart(2, '0')
          const hour = String(value.hour?.low ?? value.hour ?? 0).padStart(2, '0')
          const minute = String(value.minute?.low ?? value.minute ?? 0).padStart(2, '0')
          const second = String(value.second?.low ?? value.second ?? 0).padStart(2, '0')
          
          // Format as readable datetime
          return `${year}-${month}-${day} ${hour}:${minute}:${second}`
        } catch (e) {
          // Fallback if parsing fails
          return JSON.stringify(value, null, 2)
        }
      }
      
      // Regular object, stringify it
      return JSON.stringify(value, null, 2)
    }
    
    // Check if it's an ISO date string
    if (typeof value === 'string') {
      // Try to parse as date
      const dateMatch = value.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
      if (dateMatch) {
        try {
          const date = new Date(value)
          if (!isNaN(date.getTime())) {
            return date.toLocaleString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: false
            })
          }
        } catch (e) {
          // Not a valid date, return as-is
        }
      }
    }
    
    return String(value)
  }

  // Helper function to get node caption based on type
  const getNodeCaption = (node: GraphNode): string => {
    const nodeType = getNodeLabel(node)
    const props = node.properties
    
    switch (nodeType) {
      case 'Thread':
        return props.title ? `Thread: ${props.title.substring(0, 30)}${props.title.length > 30 ? '...' : ''}` : 'Thread'
      case 'Message':
        const sender = props.sender || 'unknown'
        const text = props.text || ''
        return `${sender}: ${text.substring(0, 30)}${text.length > 30 ? '...' : ''}`
      case 'ReasoningStep':
        const reasoning = props.reasoning_text || ''
        return `Step ${props.step_number || '?'}: ${reasoning.substring(0, 25)}${reasoning.length > 25 ? '...' : ''}`
      case 'ToolCall':
        return 'Tool Call'
      case 'Tool':
        return props.name || 'Tool'
      case 'UserPreference':
        const pref = props.preference || ''
        return pref.substring(0, 35) + (pref.length > 35 ? '...' : '')
      case 'PreferenceCategory':
        return props.name || 'Category'
      case 'Location':
        return props.name || 'Location'
      case 'Person':
        return props.name || 'Person'
      case 'Organization':
        return props.name || 'Organization'
      case 'Topic':
        return props.name || 'Topic'
      default:
        return props.name || props.title || nodeType
    }
  }
  
  // Filter nodes based on selected memory types
  const filteredNodes = useMemo(() => {
    if (!graphData) return []
    
    return graphData.nodes.filter(node => {
      const memoryType = getNodeMemoryType(node)
      return memoryFilters[memoryType]
    })
  }, [graphData, memoryFilters])

  // Filter relationships - only show if both from and to nodes are visible
  const filteredRelationships = useMemo(() => {
    if (!graphData) return []
    
    const visibleNodeIds = new Set(filteredNodes.map(n => n.id))
    
    return graphData.relationships.filter(rel => {
      return visibleNodeIds.has(rel.from) && visibleNodeIds.has(rel.to)
    })
  }, [graphData, filteredNodes])

  // Transform graph data to NVL format
  const nvlNodes = useMemo<NvlNode[]>(() => {
    if (!filteredNodes) return []
    
    return filteredNodes.map(node => {
      const nodeType = getNodeLabel(node)
      const memoryType = getNodeMemoryType(node)
      const isSelected = selectedNode?.id === node.id
      const caption = getNodeCaption(node)
      
      // Size based on node type
      let baseSize = 15
      if (nodeType === 'Thread') baseSize = 25
      else if (nodeType === 'Tool') baseSize = 22
      else if (nodeType === 'Message') baseSize = 18
      else if (nodeType === 'ReasoningStep') baseSize = 16
      else if (nodeType === 'ToolCall') baseSize = 14
      else if (nodeType === 'UserPreference') baseSize = 16
      else if (nodeType === 'PreferenceCategory') baseSize = 20
      else if (nodeType === 'Location') baseSize = 18
      else if (nodeType === 'Person') baseSize = 18
      else if (nodeType === 'Organization') baseSize = 18
      else if (nodeType === 'Topic') baseSize = 18

      return {
        id: node.id,
        caption,
        // Increase size for selected node
        size: isSelected ? baseSize + 5 : baseSize,
        color: NODE_COLORS[nodeType as keyof typeof NODE_COLORS] || '#CCCCCC',
        // Mark as selected to trigger halo effect
        selected: isSelected,
        // Store original data for click events
        data: node,
      }
    })
  }, [filteredNodes, selectedNode])

  const nvlRelationships = useMemo<NvlRelationship[]>(() => {
    if (!filteredRelationships) return []
    
    return filteredRelationships.map(rel => {
      const isSelected = selectedRelationship?.id === rel.id
      return {
      id: rel.id,
      from: rel.from,
      to: rel.to,
      caption: rel.type,
        selected: isSelected,
      }
    })
  }, [filteredRelationships, selectedRelationship])

  // Handle node and relationship click events and enable pan/zoom/drag
  const mouseEventCallbacks: MouseEventCallbacks = useMemo(() => ({
    onNodeClick: (node: NvlNode) => {
      const originalData = node.data as GraphNode
      if (originalData) {
        setSelectedNode(originalData)
        setSelectedRelationship(null) // Clear relationship selection
      }
    },
    onRelationshipClick: (rel: NvlRelationship) => {
      if (!graphData) return
      
      // Find the full relationship data
      const fullRel = graphData.relationships.find(r => r.id === rel.id)
      if (fullRel) {
        setSelectedRelationship(fullRel)
        setSelectedNode(null) // Clear node selection
      }
    },
    onPan: true, // Enable canvas panning
    onZoom: true, // Enable canvas zooming
    onDrag: true, // Enable node dragging
  }), [graphData])

  // Load data when opened
  useEffect(() => {
    if (isOpen) {
      loadGraphData()
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <>
      {/* Overlay */}
      <Box
        position="fixed"
        top={0}
        left={0}
        right={0}
        bottom={0}
        bg="blackAlpha.600"
        zIndex={1000}
        onClick={onClose}
      />

      {/* Graph View Modal */}
      <Box
        position="fixed"
        top="50%"
        left="50%"
        transform="translate(-50%, -50%)"
        width={{ base: '95%', md: '90%', lg: '85%' }}
        height={{ base: '90%', md: '85%' }}
        bg="white"
        borderRadius="xl"
        boxShadow="2xl"
        zIndex={1001}
        display="flex"
        flexDirection="column"
        overflow="hidden"
      >
        {/* Header */}
        <VStack gap={0} borderBottom="1px solid" borderColor="gray.200">
          <HStack
            justifyContent="space-between"
            p={4}
            width="100%"
            bg="gray.50"
          >
            <VStack align="start" gap={0}>
              <Text fontSize="xl" fontWeight="bold">
                Complete Memory Graph
              </Text>
              <Text fontSize="xs" color="gray.600">
                Short-term, procedural, and user profile memory with entities
              </Text>
              {graphData && (
                <HStack gap={2} mt={1}>
                  <Badge colorPalette="blue" fontSize="xs">
                    {filteredNodes.length} / {graphData.nodes.length} nodes
                  </Badge>
                  <Badge colorPalette="green" fontSize="xs">
                    {filteredRelationships.length} / {graphData.relationships.length} relationships
                  </Badge>
                </HStack>
              )}
            </VStack>

            <HStack gap={2}>
              <IconButton
                aria-label="Refresh graph"
                size="sm"
                onClick={loadGraphData}
                disabled={isLoading}
              >
                <HiRefresh />
              </IconButton>
              <IconButton
                aria-label="Close graph view"
                size="sm"
                variant="ghost"
                onClick={onClose}
              >
                <HiX />
              </IconButton>
            </HStack>
          </HStack>

          {/* Memory Type Filter Toggles */}
          <HStack
            p={3}
            width="100%"
            bg="white"
            borderTop="1px solid"
            borderColor="gray.100"
            justifyContent="center"
            gap={3}
            flexWrap="wrap"
          >
            <Text fontSize="xs" fontWeight="semibold" color="gray.600">
              Filter by Memory Type:
            </Text>
            
            {/* Short-term Memory Toggle */}
            <Button
              size="sm"
              variant={memoryFilters['short-term'] ? 'solid' : 'outline'}
              colorPalette={memoryFilters['short-term'] ? 'blue' : 'gray'}
              onClick={() => setMemoryFilters(prev => ({
                ...prev,
                'short-term': !prev['short-term']
              }))}
              leftIcon={
                <Box
                  w={3}
                  h={3}
                  borderRadius="full"
                  bg={MEMORY_TYPE_COLORS['short-term'].border}
                />
              }
            >
              Short-Term
            </Button>

            {/* User Profile Memory Toggle */}
            <Button
              size="sm"
              variant={memoryFilters['user-profile'] ? 'solid' : 'outline'}
              colorPalette={memoryFilters['user-profile'] ? 'yellow' : 'gray'}
              onClick={() => setMemoryFilters(prev => ({
                ...prev,
                'user-profile': !prev['user-profile']
              }))}
              leftIcon={
                <Box
                  w={3}
                  h={3}
                  borderRadius="full"
                  bg={MEMORY_TYPE_COLORS['user-profile'].border}
                />
              }
            >
              User Profile
            </Button>

            {/* Procedural Memory Toggle */}
            <Button
              size="sm"
              variant={memoryFilters['procedural'] ? 'solid' : 'outline'}
              colorPalette={memoryFilters['procedural'] ? 'green' : 'gray'}
              onClick={() => setMemoryFilters(prev => ({
                ...prev,
                'procedural': !prev['procedural']
              }))}
              leftIcon={
                <Box
                  w={3}
                  h={3}
                  borderRadius="full"
                  bg={MEMORY_TYPE_COLORS['procedural'].border}
                />
              }
            >
              Procedural
            </Button>

            {/* Select All / Deselect All */}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                const allEnabled = Object.values(memoryFilters).every(v => v)
                setMemoryFilters({
                  'short-term': !allEnabled,
                  'user-profile': !allEnabled,
                  'procedural': !allEnabled,
                })
              }}
            >
              {Object.values(memoryFilters).every(v => v) ? 'Deselect All' : 'Select All'}
            </Button>
          </HStack>
        </VStack>

        {/* Graph Container */}
        <Box flex={1} position="relative" bg="white">
          {isLoading ? (
            <VStack height="100%" justifyContent="center" gap={4}>
              <Spinner size="xl" />
              <Text color="gray.600">Loading memory graph...</Text>
            </VStack>
          ) : error ? (
            <VStack height="100%" justifyContent="center" gap={4} p={6}>
              <Text fontSize="lg" color="red.500" textAlign="center">
                {error}
              </Text>
              <Button colorPalette="blue" onClick={loadGraphData}>
                Try Again
              </Button>
            </VStack>
          ) : graphData && graphData.nodes.length > 0 ? (
            <Box height="100%" width="100%" position="relative">
              <Box height="100%" width="100%" style={{ touchAction: 'none' }}>
              <InteractiveNvlWrapper
                nodes={nvlNodes}
                rels={nvlRelationships}
                mouseEventCallbacks={mouseEventCallbacks}
                nvlOptions={{
                    layout: 'd3Force',
                  initialZoom: 1,
                  disableWebGL: false,
                    minZoom: 0.1,
                    maxZoom: 3,
                  }}
                />
              </Box>

              {/* Legend Panel - only show when no node is selected */}
              {!selectedNode && !selectedRelationship && (
                <Box
                  position="absolute"
                  bottom={4}
                  left={4}
                  bg="white"
                  borderRadius="md"
                  boxShadow="lg"
                  p={3}
                  border="1px solid"
                  borderColor="gray.200"
                  zIndex={10}
                  pointerEvents="auto"
                  opacity={0.95}
                  maxW="320px"
                >
                <Text fontSize="sm" fontWeight="bold" mb={2} color="gray.800">
                  Memory Types Legend
                </Text>
                <VStack align="stretch" gap={2.5} fontSize="xs">
                  {/* Short-term Memory Group */}
                  {memoryFilters['short-term'] && (
                    <Box
                      p={2}
                      borderRadius="md"
                      bg={MEMORY_TYPE_COLORS['short-term'].bg}
                      border="1px solid"
                      borderColor={MEMORY_TYPE_COLORS['short-term'].border}
                    >
                      <Text fontSize="xs" fontWeight="bold" color="gray.800" mb={1}>
                        {MEMORY_TYPE_COLORS['short-term'].label}
                      </Text>
                      <VStack align="stretch" gap={1}>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.Thread} flexShrink={0} />
                          <Text color="gray.700">Thread</Text>
                        </HStack>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.Message} flexShrink={0} />
                          <Text color="gray.700">Message</Text>
                        </HStack>
                      </VStack>
                    </Box>
                  )}

                  {/* User Profile Memory Group */}
                  {memoryFilters['user-profile'] && (
                    <Box
                      p={2}
                      borderRadius="md"
                      bg={MEMORY_TYPE_COLORS['user-profile'].bg}
                      border="1px solid"
                      borderColor={MEMORY_TYPE_COLORS['user-profile'].border}
                    >
                      <Text fontSize="xs" fontWeight="bold" color="gray.800" mb={1}>
                        {MEMORY_TYPE_COLORS['user-profile'].label}
                      </Text>
                      <VStack align="stretch" gap={1}>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.UserPreference} flexShrink={0} />
                          <Text color="gray.700">User Preference</Text>
                        </HStack>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.PreferenceCategory} flexShrink={0} />
                          <Text color="gray.700">Category</Text>
                        </HStack>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.Location} flexShrink={0} />
                          <Text color="gray.700">Location</Text>
                        </HStack>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.Person} flexShrink={0} />
                          <Text color="gray.700">Person</Text>
                        </HStack>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.Organization} flexShrink={0} />
                          <Text color="gray.700">Organization</Text>
                        </HStack>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.Topic} flexShrink={0} />
                          <Text color="gray.700">Topic</Text>
                        </HStack>
                      </VStack>
                    </Box>
                  )}

                  {/* Procedural Memory Group */}
                  {memoryFilters['procedural'] && (
                    <Box
                      p={2}
                      borderRadius="md"
                      bg={MEMORY_TYPE_COLORS['procedural'].bg}
                      border="1px solid"
                      borderColor={MEMORY_TYPE_COLORS['procedural'].border}
                    >
                      <Text fontSize="xs" fontWeight="bold" color="gray.800" mb={1}>
                        {MEMORY_TYPE_COLORS['procedural'].label}
                      </Text>
                      <VStack align="stretch" gap={1}>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.ReasoningStep} flexShrink={0} />
                          <Text color="gray.700">Reasoning Step</Text>
                        </HStack>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.ToolCall} flexShrink={0} />
                          <Text color="gray.700">Tool Call</Text>
                        </HStack>
                        <HStack gap={2}>
                          <Box w={3} h={3} borderRadius="full" bg={NODE_COLORS.Tool} flexShrink={0} />
                          <Text color="gray.700">Tool</Text>
                        </HStack>
                      </VStack>
                    </Box>
                  )}
                </VStack>
              </Box>
              )}

              {/* Property Panel for Selected Node or Relationship */}
              {(selectedNode || selectedRelationship) && (
                <Box
                  position="absolute"
                  top={4}
                  left={4}
                  bg="white"
                  borderRadius="md"
                  boxShadow="xl"
                  p={4}
                  w="320px"
                  h="500px"
                  border="1px solid"
                  borderColor="gray.200"
                  zIndex={10}
                  pointerEvents="auto"
                  display="flex"
                  flexDirection="column"
                  opacity={0.95}
                >
                  {/* Fixed Header */}
                  <HStack justifyContent="space-between" mb={3}>
                    <Text fontSize="md" fontWeight="bold" color="gray.800">
                      {selectedNode ? 'Node Properties' : 'Relationship Properties'}
                    </Text>
                    <IconButton
                      aria-label="Close properties"
                      size="xs"
                      variant="ghost"
                      onClick={() => {
                        setSelectedNode(null)
                        setSelectedRelationship(null)
                      }}
                    >
                      <HiX />
                    </IconButton>
                  </HStack>

                  {/* Scrollable Content */}
                  <Box flex={1} overflowY="auto" pr={1}>
                    <VStack align="stretch" gap={3}>
                      {selectedNode ? (
                        <>
                          {/* Node Type & Color */}
                          <Box>
                            <Text fontSize="xs" fontWeight="semibold" color="gray.600" mb={1}>
                              Type & Color
                            </Text>
                            <HStack gap={2} align="center">
                              <Box 
                                w={6} 
                                h={6} 
                                borderRadius="full" 
                                bg={NODE_COLORS[getNodeLabel(selectedNode) as keyof typeof NODE_COLORS] || '#CCCCCC'}
                                border="1px solid"
                                borderColor="gray.300"
                              />
                              <Text fontSize="sm" color="gray.800" fontWeight="medium">
                                {getNodeLabel(selectedNode)}
                              </Text>
                            </HStack>
                          </Box>

                          {/* Node Labels */}
                          <Box>
                            <Text fontSize="xs" fontWeight="semibold" color="gray.600" mb={1}>
                              Labels
                            </Text>
                            <HStack gap={1} flexWrap="wrap">
                              {selectedNode.labels.map((label) => (
                                <Badge key={label} colorPalette="purple" size="sm">
                                  {label}
                                </Badge>
                              ))}
                            </HStack>
                          </Box>

                          {/* Node Properties */}
                          <Box>
                            <Text fontSize="xs" fontWeight="semibold" color="gray.600" mb={1}>
                              Properties
                            </Text>
                            <VStack align="stretch" gap={2}>
                              {Object.entries(selectedNode.properties).map(([key, value]) => (
                                <Box key={key}>
                                  <Text fontSize="xs" fontWeight="medium" color="gray.700">
                                    {key}
                                  </Text>
                                  <Text
                                    fontSize="xs"
                                    color="gray.600"
                                    mt={0.5}
                                    wordBreak="break-word"
                                    whiteSpace="pre-wrap"
                                  >
                                    {formatPropertyValue(value)}
                                  </Text>
                                </Box>
                              ))}
                            </VStack>
                          </Box>
                        </>
                      ) : selectedRelationship && graphData ? (
                        <>
                          {/* Relationship Type */}
                          <Box>
                            <Text fontSize="xs" fontWeight="semibold" color="gray.600" mb={1}>
                              Type
                            </Text>
                            <Badge colorPalette="green" size="sm">
                              {selectedRelationship.type}
                            </Badge>
                          </Box>

                          {/* Connected Nodes */}
                          <Box>
                            <Text fontSize="xs" fontWeight="semibold" color="gray.600" mb={1}>
                              Connection
                            </Text>
                            <VStack align="stretch" gap={2}>
                              {(() => {
                                const fromNode = graphData.nodes.find(n => n.id === selectedRelationship.from)
                                const toNode = graphData.nodes.find(n => n.id === selectedRelationship.to)
                                
                                return (
                                  <>
                                    <Box>
                                      <Text fontSize="xs" color="gray.500">From:</Text>
                                      <Text fontSize="xs" color="gray.700" fontWeight="medium" mt={0.5}>
                                        {fromNode?.labels.join(', ')}
                                      </Text>
                                      <Text fontSize="xs" color="gray.600" mt={0.5}>
                                        {fromNode?.properties.name || fromNode?.properties.preference?.substring(0, 40) || fromNode?.id}
                                      </Text>
                                    </Box>
                                    <Box>
                                      <Text fontSize="xs" color="gray.500">To:</Text>
                                      <Text fontSize="xs" color="gray.700" fontWeight="medium" mt={0.5}>
                                        {toNode?.labels.join(', ')}
                                      </Text>
                                      <Text fontSize="xs" color="gray.600" mt={0.5}>
                                        {toNode?.properties.name || toNode?.properties.preference?.substring(0, 40) || toNode?.id}
                                      </Text>
                                    </Box>
                                  </>
                                )
                              })()}
                            </VStack>
                          </Box>

                          {/* Relationship Properties */}
                          {Object.keys(selectedRelationship.properties).length > 0 && (
                            <Box>
                              <Text fontSize="xs" fontWeight="semibold" color="gray.600" mb={1}>
                                Properties
                              </Text>
                              <VStack align="stretch" gap={2}>
                                {Object.entries(selectedRelationship.properties).map(([key, value]) => (
                                  <Box key={key}>
                                    <Text fontSize="xs" fontWeight="medium" color="gray.700">
                                      {key}
                                    </Text>
                                    <Text
                                      fontSize="xs"
                                      color="gray.600"
                                      mt={0.5}
                                      wordBreak="break-word"
                                      whiteSpace="pre-wrap"
                                    >
                                      {formatPropertyValue(value)}
                                    </Text>
                                  </Box>
                                ))}
                              </VStack>
                            </Box>
                          )}
                        </>
                      ) : null}
                    </VStack>
                  </Box>
                </Box>
              )}

              {/* Scene Overview Panel */}
              <Box
                position="absolute"
                top={4}
                right={4}
                bg="white"
                borderRadius="md"
                boxShadow="lg"
                p={4}
                w="320px"
                h="500px"
                opacity={0.95}
                border="1px solid"
                borderColor="gray.200"
                zIndex={10}
                pointerEvents="auto"
                display="flex"
                flexDirection="column"
              >
                {/* Fixed Header */}
                <VStack align="stretch" mb={3} gap={1}>
                  <Text fontSize="sm" fontWeight="bold" color="gray.700">
                    Scene Overview
                  </Text>
                  <Text fontSize="xs" color="gray.500">
                    Showing {filteredNodes.length} nodes, {filteredRelationships.length} relationships
                  </Text>
                </VStack>

                {/* Scrollable Content */}
                <Box flex={1} overflowY="auto" pr={1}>
                  <VStack align="stretch" gap={3}>
                    {/* Group nodes by memory type */}
                    {memoryFilters['short-term'] && (
                      <Box>
                        <HStack mb={1} gap={2}>
                          <Box
                            w={2.5}
                            h={2.5}
                            borderRadius="sm"
                            bg={MEMORY_TYPE_COLORS['short-term'].border}
                          />
                          <Text fontSize="xs" fontWeight="semibold" color="gray.600">
                            Short-Term Memory
                          </Text>
                        </HStack>
                        <VStack align="stretch" gap={0.5} pl={4}>
                          {Object.entries(graphStats.nodes)
                            .filter(([label]) => label === 'Thread' || label === 'Message')
                            .map(([label, count]) => {
                              const color = NODE_COLORS[label as keyof typeof NODE_COLORS] || '#CCCCCC'
                              return (
                                <HStack key={label} justifyContent="space-between" fontSize="xs">
                                  <HStack gap={1.5}>
                                    <Box w={2.5} h={2.5} borderRadius="full" bg={color} flexShrink={0} />
                                    <Text color="gray.700">{label}</Text>
                                  </HStack>
                                  <Badge colorPalette="blue" size="sm">{count}</Badge>
                                </HStack>
                              )
                            })}
                        </VStack>
                      </Box>
                    )}

                    {memoryFilters['user-profile'] && (
                      <Box>
                        <HStack mb={1} gap={2}>
                          <Box
                            w={2.5}
                            h={2.5}
                            borderRadius="sm"
                            bg={MEMORY_TYPE_COLORS['user-profile'].border}
                          />
                          <Text fontSize="xs" fontWeight="semibold" color="gray.600">
                            User Profile Memory
                          </Text>
                        </HStack>
                        <VStack align="stretch" gap={0.5} pl={4}>
                          {Object.entries(graphStats.nodes)
                            .filter(([label]) => 
                              label === 'UserPreference' || label === 'PreferenceCategory' ||
                              label === 'Location' || label === 'Person' || 
                              label === 'Organization' || label === 'Topic'
                            )
                            .map(([label, count]) => {
                              const color = NODE_COLORS[label as keyof typeof NODE_COLORS] || '#CCCCCC'
                              return (
                                <HStack key={label} justifyContent="space-between" fontSize="xs">
                                  <HStack gap={1.5}>
                                    <Box w={2.5} h={2.5} borderRadius="full" bg={color} flexShrink={0} />
                                    <Text color="gray.700">{label}</Text>
                                  </HStack>
                                  <Badge colorPalette="yellow" size="sm">{count}</Badge>
                                </HStack>
                              )
                            })}
                        </VStack>
                      </Box>
                    )}

                    {memoryFilters['procedural'] && (
                      <Box>
                        <HStack mb={1} gap={2}>
                          <Box
                            w={2.5}
                            h={2.5}
                            borderRadius="sm"
                            bg={MEMORY_TYPE_COLORS['procedural'].border}
                          />
                          <Text fontSize="xs" fontWeight="semibold" color="gray.600">
                            Procedural Memory
                          </Text>
                        </HStack>
                        <VStack align="stretch" gap={0.5} pl={4}>
                          {Object.entries(graphStats.nodes)
                            .filter(([label]) => 
                              label === 'ReasoningStep' || label === 'ToolCall' || label === 'Tool'
                            )
                            .map(([label, count]) => {
                              const color = NODE_COLORS[label as keyof typeof NODE_COLORS] || '#CCCCCC'
                              return (
                                <HStack key={label} justifyContent="space-between" fontSize="xs">
                                  <HStack gap={1.5}>
                                    <Box w={2.5} h={2.5} borderRadius="full" bg={color} flexShrink={0} />
                                    <Text color="gray.700">{label}</Text>
                                  </HStack>
                                  <Badge colorPalette="green" size="sm">{count}</Badge>
                                </HStack>
                              )
                            })}
                        </VStack>
                      </Box>
                    )}

                    {/* Relationship Statistics */}
                    {Object.keys(graphStats.relationships).length > 0 && (
                      <Box>
                        <Text fontSize="xs" fontWeight="semibold" color="gray.600" mb={1}>
                          Relationships
                        </Text>
                        <VStack align="stretch" gap={0.5} pl={2}>
                          {Object.entries(graphStats.relationships).map(([type, count]) => (
                            <HStack key={type} justifyContent="space-between" fontSize="xs">
                              <Text color="gray.700">{type}</Text>
                              <Badge colorPalette="gray" size="sm">{count}</Badge>
                            </HStack>
                          ))}
                        </VStack>
                      </Box>
                    )}
                  </VStack>
                </Box>
              </Box>
            </Box>
          ) : null}
        </Box>

        {/* Legend */}
        {graphData && graphData.nodes.length > 0 && !isLoading && !error && (
          <HStack
            p={4}
            borderTop="1px solid"
            borderColor="gray.200"
            justifyContent="center"
            gap={6}
            flexWrap="wrap"
            bg="gray.50"
          >
            <HStack>
              <Box w={4} h={4} borderRadius="full" bg="#FFDF81" />
              <Text fontSize="sm">User Preferences</Text>
            </HStack>
            <HStack>
              <Box w={4} h={4} borderRadius="full" bg="#8FE3E8" />
              <Text fontSize="sm">Categories</Text>
            </HStack>
            <HStack>
              <Box w={8} h={0.5} bg="#8884d8" />
              <Text fontSize="sm">IN_CATEGORY</Text>
            </HStack>
            <Text fontSize="xs" color="gray.600">
              Click nodes or relationships to view details • Selected items have a halo • Drag to pan • Scroll to zoom
            </Text>
          </HStack>
        )}
      </Box>
    </>
  )
}
