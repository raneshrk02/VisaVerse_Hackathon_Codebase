import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Settings2, ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { apiClient } from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";
import { SourceCard } from "@/components/SourceCard";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  sources?: Array<{
    content: string;
    metadata: Record<string, any>;
    source_class?: number | null;
    rank: number;
  }>;
  confidence?: number;
  processing_time?: number;
  cache_hit?: boolean;
}

interface ChatResponse {
  answer: string;
  sources?: Array<{
    content: string;
    metadata: Record<string, any>;
    source_class?: number | null;
    rank: number;
  }>;
  confidence?: number;
  processing_time?: number;
  cache_hit?: boolean;
  conversation_id?: string;
}

export default function Chat() {
  const [inputMessage, setInputMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [conversationSummary, setConversationSummary] = useState<string>("");
  
  // Settings
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [classNum, setClassNum] = useState<string>("");
  const [includeSources, setIncludeSources] = useState(true);
  const [maxSources, setMaxSources] = useState(5);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const resetConversation = () => {
    setMessages([]);
    setConversationId(null);
    setConversationSummary("");
    toast({
      title: "Conversation reset",
      description: "Starting a new conversation",
    });
  };

  // Function to create a concise summary of the previous Q&A exchange
  const createConversationSummary = (userQuestion: string, assistantAnswer: string): string => {
    // Extract key information from the exchange
    // Keep it very concise - just the essential context
    const answerPreview = assistantAnswer.slice(0, 200).trim(); // First 200 chars
    
    // Create a compact summary
    const summary = `Previous Q: ${userQuestion}\nPrevious A: ${answerPreview}${assistantAnswer.length > 200 ? '...' : ''}`;
    
    return summary;
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || loading) return;

    const userMessage: Message = {
      role: "user",
      content: inputMessage.trim(),
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage("");
    setLoading(true);

    const startTime = Date.now();

    try {
      // Instead of sending full conversation history, send only the compact summary
      const conversationHistory = conversationSummary ? [
        {
          role: "system" as const,
          content: conversationSummary,
          timestamp: Date.now()
        }
      ] : [];

      const body = {
        message: userMessage.content,
        class_num: classNum ? parseInt(classNum) : null,
        conversation_history: conversationHistory,
        include_sources: includeSources,
        max_sources: maxSources,
      };

      // Use streaming endpoint (via Vite proxy in dev, direct in production)
      const response = await fetch('/api/v1/chat/ask/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let accumulatedAnswer = '';
      let sources: any[] = [];
      let metadata: any = {};

      // Create initial assistant message
      const assistantMessage: Message = {
        role: "assistant",
        content: '',
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, assistantMessage]);

      // Read the stream
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        // Decode the chunk
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'status') {
                // Show status in toast
                toast({
                  title: "Processing",
                  description: data.message,
                });
              } else if (data.type === 'sources') {
                sources = data.sources;
              } else if (data.type === 'token') {
                // Accumulate tokens
                accumulatedAnswer += data.content;
                
                // Update the assistant message in real-time
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage.role === 'assistant') {
                    lastMessage.content = accumulatedAnswer;
                    lastMessage.sources = sources;
                  }
                  return newMessages;
                });
              } else if (data.type === 'metadata') {
                metadata = data;
              } else if (data.type === 'error') {
                throw new Error(data.error);
              } else if (data.done) {
                // Final update with all metadata
                const duration = ((Date.now() - startTime) / 1000).toFixed(2);
                
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage.role === 'assistant') {
                    lastMessage.content = accumulatedAnswer;
                    lastMessage.sources = sources;
                    lastMessage.processing_time = metadata.processing_time;
                  }
                  return newMessages;
                });

                // Generate summary of this exchange for the next question
                const newSummary = createConversationSummary(userMessage.content, accumulatedAnswer);
                setConversationSummary(newSummary);
                console.log('Generated conversation summary:', newSummary);

                toast({
                  title: "Response received",
                  // description: `Processing time: ${duration}s`, // Hidden per user request
                });
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError);
            }
          }
        }
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to send message";
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
      
      // Remove the user message and incomplete assistant message if there was an error
      setMessages(prev => prev.slice(0, -2));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="h-[calc(100vh-12rem)] flex flex-col max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-3xl font-bold">Chat</h1>
          <p className="text-sm text-muted-foreground">
            {conversationId ? "Conversation in progress" : "Start a new conversation"}
            {conversationSummary && (
              <Badge variant="secondary" className="ml-2 text-xs">
                Context active
              </Badge>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          {Array.isArray(messages) && messages.length > 0 && (
            <Button variant="outline" size="sm" onClick={resetConversation}>
              <RotateCcw className="h-4 w-4 mr-2" />
              New Chat
            </Button>
          )}
          <Collapsible open={settingsOpen} onOpenChange={setSettingsOpen}>
            <CollapsibleTrigger asChild>
              <Button variant="outline" size="sm">
                <Settings2 className="h-4 w-4 mr-2" />
                Settings
                {settingsOpen ? (
                  <ChevronUp className="h-4 w-4 ml-2" />
                ) : (
                  <ChevronDown className="h-4 w-4 ml-2" />
                )}
              </Button>
            </CollapsibleTrigger>
          </Collapsible>
        </div>
      </div>

      <Collapsible open={settingsOpen} onOpenChange={setSettingsOpen}>
        <CollapsibleContent>
          <Card className="mb-4">
            <CardContent className="pt-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="class-num-setting">Class Number (1-12)</Label>
                  <Input
                    id="class-num-setting"
                    type="number"
                    min="1"
                    max="12"
                    value={classNum}
                    onChange={(e) => setClassNum(e.target.value)}
                    placeholder="Optional"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="max-sources-setting">Max Sources</Label>
                  <Input
                    id="max-sources-setting"
                    type="number"
                    min="1"
                    max="10"
                    value={maxSources}
                    onChange={(e) => setMaxSources(parseInt(e.target.value))}
                  />
                </div>

                <div className="flex items-end">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="include-sources-setting"
                      checked={includeSources}
                      onCheckedChange={(checked) => setIncludeSources(checked as boolean)}
                    />
                    <Label htmlFor="include-sources-setting" className="cursor-pointer">
                      Include sources
                    </Label>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </CollapsibleContent>
      </Collapsible>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto border rounded-lg bg-card mb-4 p-4 space-y-4">
  {Array.isArray(messages) && messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center">
            <div className="space-y-2">
              <h3 className="text-lg font-medium text-muted-foreground">No messages yet</h3>
              <p className="text-sm text-muted-foreground">
                Start by asking a question below
              </p>
            </div>
          </div>
        ) : (
          <>
            {Array.isArray(messages) && messages.map((msg, idx) => (
              <div key={idx} className="space-y-2">
                {msg.role === "user" ? (
                  <div className="flex justify-end">
                    <div className="bg-primary text-primary-foreground rounded-lg px-4 py-2 max-w-[80%]">
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-start">
                    <div className="space-y-3 max-w-[85%]">
                      <div className="bg-muted rounded-lg px-4 py-3">
                        <div className="prose prose-sm max-w-none dark:prose-invert">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      </div>

                      {/* Processing time badge hidden per user request
                      <div className="flex flex-wrap gap-2 px-2">
                        {msg.processing_time !== undefined && (
                          <Badge variant="outline" className="text-xs">
                            {msg.processing_time.toFixed(2)}s
                          </Badge>
                        )}
                      </div>
                      */}

                      {Array.isArray(msg.sources) && msg.sources.length > 0 && (
                        <div className="space-y-2 px-2">
                          <Collapsible>
                            <CollapsibleTrigger asChild>
                              <Button variant="ghost" size="sm" className="text-xs">
                                <ChevronDown className="h-3 w-3 mr-1" />
                                View Sources ({Array.isArray(msg.sources) ? msg.sources.length : 0})
                              </Button>
                            </CollapsibleTrigger>
                            <CollapsibleContent className="mt-2 space-y-2">
                              {Array.isArray(msg.sources) && msg.sources.map((source, sidx) => (
                                <SourceCard key={sidx} source={source} />
                              ))}
                            </CollapsibleContent>
                          </Collapsible>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-lg px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <div className="flex gap-2">
        <Input
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
          disabled={loading}
          className="flex-1"
        />
        <Button onClick={sendMessage} disabled={loading || !inputMessage.trim()}>
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  );
}
