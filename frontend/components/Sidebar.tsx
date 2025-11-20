'use client'

import { useState } from 'react'
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  IconButton,
  Spinner,
} from '@chakra-ui/react'
import { HiOutlineTrash, HiPlus, HiX, HiMenu } from 'react-icons/hi'
import { chatAPI, ThreadInfo } from '@/lib/api'
import { toaster } from '@/components/ui/toaster'

interface SidebarProps {
  threads: ThreadInfo[]
  activeThreadId: string | null
  isOpen: boolean
  onToggle: () => void
  onSelectThread: (threadId: string) => void
  onNewThread: () => void
  onDeleteThread: (threadId: string) => void
  onThreadsUpdate: () => void
}

export default function Sidebar({
  threads,
  activeThreadId,
  isOpen,
  onToggle,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onThreadsUpdate,
}: SidebarProps) {
  const [deletingThreadId, setDeletingThreadId] = useState<string | null>(null)

  const handleDeleteThread = async (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (deletingThreadId) return
    
    try {
      setDeletingThreadId(threadId)
      await chatAPI.deleteThread(threadId)
      toaster.create({
        title: 'Thread Deleted',
        description: 'Thread has been deleted successfully',
        type: 'success',
        duration: 2000,
      })
      onDeleteThread(threadId)
    } catch (error) {
      toaster.create({
        title: 'Delete Failed',
        description: 'Failed to delete thread',
        type: 'error',
        duration: 5000,
      })
    } finally {
      setDeletingThreadId(null)
    }
  }

  const formatTimestamp = (timestamp: string | null | undefined) => {
    if (!timestamp) return ''
    try {
      const date = new Date(timestamp)
      const now = new Date()
      const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)
      
      if (diffInHours < 1) {
        return 'Just now'
      } else if (diffInHours < 24) {
        return `${Math.floor(diffInHours)}h ago`
      } else if (diffInHours < 168) { // 7 days
        return `${Math.floor(diffInHours / 24)}d ago`
      } else {
        return date.toLocaleDateString()
      }
    } catch {
      return ''
    }
  }

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <Box
          position="fixed"
          top={0}
          left={0}
          right={0}
          bottom={0}
          bg="blackAlpha.600"
          zIndex={998}
          display={{ base: 'block', md: 'none' }}
          onClick={onToggle}
        />
      )}

      {/* Toggle button - visible when closed on all screens */}
      {!isOpen && (
        <IconButton
          aria-label="Open sidebar"
          position="fixed"
          top={4}
          left={4}
          zIndex={999}
          onClick={onToggle}
          colorPalette="blue"
          variant="solid"
        >
          <HiMenu />
        </IconButton>
      )}

      {/* Sidebar */}
      <Box
        position="fixed"
        top={0}
        left={isOpen ? 0 : '-300px'}
        height="100vh"
        width="300px"
        bg="white"
        borderRight="1px solid"
        borderColor="gray.200"
        boxShadow="lg"
        zIndex={999}
        transition="left 0.3s ease"
        overflowY="auto"
      >
        <VStack align="stretch" gap={0} height="100%">
          {/* Header */}
          <HStack
            justifyContent="space-between"
            p={4}
            borderBottom="1px solid"
            borderColor="gray.200"
          >
            <Text fontSize="lg" fontWeight="bold">
              Conversations
            </Text>
            <IconButton
              aria-label="Close sidebar"
              size="sm"
              variant="ghost"
              onClick={onToggle}
            >
              <HiX />
            </IconButton>
          </HStack>

          {/* New Thread Button */}
          <Box p={4} borderBottom="1px solid" borderColor="gray.200">
            <Button
              width="100%"
              colorPalette="blue"
              onClick={onNewThread}
              leftIcon={<HiPlus />}
            >
              New Conversation
            </Button>
          </Box>

          {/* Threads List */}
          <VStack align="stretch" gap={0} flex={1} overflowY="auto">
            {threads.length === 0 ? (
              <Box p={4} textAlign="center">
                <Text color="gray.500" fontSize="sm">
                  No conversations yet
                </Text>
              </Box>
            ) : (
              threads.map((thread) => (
                <Box
                  key={thread.id}
                  position="relative"
                  role="group"
                  _hover={{ bg: 'gray.50' }}
                >
                  <HStack
                    p={3}
                    cursor="pointer"
                    onClick={() => onSelectThread(thread.id)}
                    bg={activeThreadId === thread.id ? 'blue.50' : 'transparent'}
                    borderLeft="3px solid"
                    borderColor={
                      activeThreadId === thread.id ? 'blue.500' : 'transparent'
                    }
                    spacing={2}
                  >
                    <VStack align="stretch" flex={1} gap={1} minW={0}>
                      <Text
                        fontSize="sm"
                        fontWeight={activeThreadId === thread.id ? 'bold' : 'medium'}
                        noOfLines={2}
                        wordBreak="break-word"
                      >
                        {thread.title}
                      </Text>
                      <HStack fontSize="xs" color="gray.500" spacing={2}>
                        <Text>{thread.message_count} messages</Text>
                        <Text>•</Text>
                        <Text>{formatTimestamp(thread.last_message_at)}</Text>
                      </HStack>
                    </VStack>
                    
                    {/* Delete button - shows on hover */}
                    <IconButton
                      aria-label="Delete thread"
                      size="xs"
                      variant="ghost"
                      colorPalette="red"
                      onClick={(e) => handleDeleteThread(thread.id, e)}
                      opacity={{ base: 1, md: 0 }}
                      _groupHover={{ opacity: 1 }}
                      transition="opacity 0.2s"
                      disabled={deletingThreadId === thread.id}
                    >
                      {deletingThreadId === thread.id ? (
                        <Spinner size="xs" />
                      ) : (
                        <HiOutlineTrash />
                      )}
                    </IconButton>
                  </HStack>
                </Box>
              ))
            )}
          </VStack>
        </VStack>
      </Box>
    </>
  )
}

