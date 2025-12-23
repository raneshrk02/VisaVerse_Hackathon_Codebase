import { useState } from "react";
import { Search as SearchIcon, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiClient } from "@/lib/api-client";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "@/hooks/use-toast";
import { SourceCard } from "@/components/SourceCard";

interface SearchResult {
  content: string;
  metadata: Record<string, any>;
  rank: number;
}

interface TopicResult {
  subject: string;
  content_preview: string;
  metadata?: Record<string, any>;
  full_text?: string;
}

interface ClassOverview {
  class_num: number;
  status: string;
  document_count: number;
  subjects: string[];
  sample_topics: Array<{
    subject: string;
    content_preview: string;
  }>;
}

export default function Search() {
  const [docQuery, setDocQuery] = useState("");
  const [docClassNum, setDocClassNum] = useState("");
  const [docTopK, setDocTopK] = useState(10);
  const [docThreshold, setDocThreshold] = useState(0.5);
  const [docLoading, setDocLoading] = useState(false);
  const [docResults, setDocResults] = useState<{ results: SearchResult[]; total: number; time: number } | null>(null);

  const [topicQuery, setTopicQuery] = useState("");
  const [topicClassNum, setTopicClassNum] = useState("");
  const [topicLimit, setTopicLimit] = useState(5);
  const [topicLoading, setTopicLoading] = useState(false);
  const [topicResults, setTopicResults] = useState<TopicResult[] | null>(null);

  const [overviewClass, setOverviewClass] = useState("");
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overview, setOverview] = useState<ClassOverview | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<TopicResult | null>(null);

  const handleDocSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docQuery.trim()) return;

    setDocLoading(true);
    const startTime = Date.now();

    try {
      const body: any = {
        question: docQuery.trim(),
        top_k: docTopK,
        similarity_threshold: docThreshold,
      };

      if (docClassNum) {
        body.class_num = parseInt(docClassNum);
      }

      const result = await apiClient.post<{ results: SearchResult[]; total_results: number; processing_time: number }>(
        "/api/v1/search/documents",
        body
      );

      const duration = ((Date.now() - startTime) / 1000).toFixed(2);
      toast({
        title: "Search complete",
        description: `Found ${result.total_results} results in ${duration}s`,
      });

      setDocResults({
        results: result.results,
        total: result.total_results,
        time: result.processing_time,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Search failed",
        variant: "destructive",
      });
    } finally {
      setDocLoading(false);
    }
  };

  const handleTopicSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicQuery.trim()) return;

    setTopicLoading(true);

    try {
      const params: any = {
        topic: topicQuery.trim(),
        limit: topicLimit,
      };

      if (topicClassNum) {
        params.class_num = parseInt(topicClassNum);
      }

      const resultAny = await apiClient.get<any>("/api/v1/search/topics", { params });

      // Backend may return either { topics: [...] } or a QueryResponse-like payload with `results`
      let topics: TopicResult[] = [];

      if (Array.isArray(resultAny.topics)) {
        topics = resultAny.topics;
      } else if (Array.isArray(resultAny.results)) {
        // Convert search results to TopicResult shape
        topics = resultAny.results.map((r: any) => ({
          subject: (r.metadata && (r.metadata.subject || r.metadata.topic)) || 'general',
          content_preview: (r.content && r.content.slice ? (r.content.slice(0, 300) + (r.content.length > 300 ? '...' : '')) : String(r.content || '')),
          metadata: r.metadata || {},
          full_text: typeof r.content === 'string' ? r.content : undefined,
        }));
      }

      toast({
        title: "Topics found",
        description: `Retrieved ${topics.length} topics`,
      });

      setTopicResults(topics);
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Topic search failed",
        variant: "destructive",
      });
    } finally {
      setTopicLoading(false);
    }
  };

  const handleClassOverview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!overviewClass) return;

    setOverviewLoading(true);

    try {
      const classNum = parseInt(overviewClass);
      const result = await apiClient.get<ClassOverview>(`/api/v1/search/class/${classNum}/overview`);

      toast({
        title: "Overview loaded",
        description: `Class ${classNum} has ${result.document_count} documents`,
      });

      setOverview(result);
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load overview",
        variant: "destructive",
      });
    } finally {
      setOverviewLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Search</h1>
        <p className="text-muted-foreground">Find documents, topics, and class information</p>
      </div>

      <Tabs defaultValue="documents" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="documents">Document Search</TabsTrigger>
          <TabsTrigger value="topics">Topic Search</TabsTrigger>
          <TabsTrigger value="overview">Class Overview</TabsTrigger>
        </TabsList>

        <TabsContent value="documents" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Document Search</CardTitle>
              <CardDescription>Search for documents by semantic similarity</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleDocSearch} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="doc-query">Search Query *</Label>
                  <Input
                    id="doc-query"
                    value={docQuery}
                    onChange={(e) => setDocQuery(e.target.value)}
                    placeholder="Enter your search query..."
                    required
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="doc-class">Class Number (1-12)</Label>
                    <Input
                      id="doc-class"
                      type="number"
                      min="1"
                      max="12"
                      value={docClassNum}
                      onChange={(e) => setDocClassNum(e.target.value)}
                      placeholder="Optional"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="doc-topk">Top K Results</Label>
                    <Input
                      id="doc-topk"
                      type="number"
                      min="1"
                      max="20"
                      value={docTopK}
                      onChange={(e) => setDocTopK(parseInt(e.target.value))}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="doc-threshold">Similarity Threshold</Label>
                    <Input
                      id="doc-threshold"
                      type="number"
                      step="0.1"
                      min="0"
                      max="1"
                      value={docThreshold}
                      onChange={(e) => setDocThreshold(parseFloat(e.target.value))}
                    />
                  </div>
                </div>

                <Button type="submit" disabled={docLoading} className="w-full">
                  {docLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <SearchIcon className="mr-2 h-4 w-4" />
                      Search Documents
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {docResults && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold">Results</h2>
                <Badge variant="secondary">{docResults.total} found</Badge>
                <Badge variant="outline">{docResults.time.toFixed(2)}s</Badge>
              </div>
              {docResults.results.map((result, idx) => (
                <SourceCard
                  key={idx}
                  source={{
                    content: result.content,
                    metadata: result.metadata,
                    rank: result.rank,
                  }}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="topics" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Topic Search</CardTitle>
              <CardDescription>Find topics by keyword</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleTopicSearch} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="topic-query">Topic *</Label>
                  <Input
                    id="topic-query"
                    value={topicQuery}
                    onChange={(e) => setTopicQuery(e.target.value)}
                    placeholder="Enter topic keyword..."
                    required
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="topic-class">Class Number (1-12)</Label>
                    <Input
                      id="topic-class"
                      type="number"
                      min="1"
                      max="12"
                      value={topicClassNum}
                      onChange={(e) => setTopicClassNum(e.target.value)}
                      placeholder="Optional"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="topic-limit">Limit</Label>
                    <Input
                      id="topic-limit"
                      type="number"
                      min="1"
                      max="20"
                      value={topicLimit}
                      onChange={(e) => setTopicLimit(parseInt(e.target.value))}
                    />
                  </div>
                </div>

                <Button type="submit" disabled={topicLoading} className="w-full">
                  {topicLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <SearchIcon className="mr-2 h-4 w-4" />
                      Search Topics
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {topicResults && (
            <div className="space-y-3">
              <h2 className="text-xl font-semibold">Topics ({topicResults.length})</h2>
              {topicResults.map((topic, idx) => (
                <Card key={idx}>
                  <CardHeader>
                    <div className="flex items-center justify-between w-full">
                      <CardTitle className="text-base">{topic.subject}</CardTitle>
                      <div>
                        <Button size="sm" variant="ghost" onClick={() => { setSelectedTopic(topic); setDialogOpen(true); }}>
                          View Full
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{topic.content_preview}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Topic full-text dialog */}
        <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open) setSelectedTopic(null); setDialogOpen(open); }}>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>{selectedTopic?.subject}</DialogTitle>
              <DialogDescription>
                {selectedTopic?.metadata && selectedTopic.metadata.subject ? selectedTopic.metadata.subject : "Full topic text"}
              </DialogDescription>
            </DialogHeader>

            <div className="py-2 max-h-[70vh] overflow-y-auto">
              <div className="prose max-w-none dark:prose-invert whitespace-pre-wrap">
                {selectedTopic ? (selectedTopic.full_text || selectedTopic.metadata?.full_text || selectedTopic.content_preview) : ""}
              </div>
            </div>
          </DialogContent>
        </Dialog>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Class Overview</CardTitle>
              <CardDescription>Get detailed information about a specific class</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleClassOverview} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="overview-class">Class Number (1-12) *</Label>
                  <Input
                    id="overview-class"
                    type="number"
                    min="1"
                    max="12"
                    value={overviewClass}
                    onChange={(e) => setOverviewClass(e.target.value)}
                    placeholder="Enter class number..."
                    required
                  />
                </div>

                <Button type="submit" disabled={overviewLoading} className="w-full">
                  {overviewLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    <>
                      <SearchIcon className="mr-2 h-4 w-4" />
                      Load Overview
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {overview && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Class {overview.class_num} Overview</CardTitle>
                  <Badge variant={overview.status === "available" ? "default" : "secondary"}>
                    {overview.status}
                  </Badge>
                </div>
                <CardDescription>
                  {overview.document_count} documents available
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {overview.subjects.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium mb-2">Subjects:</h3>
                    <div className="flex flex-wrap gap-2">
                      {overview.subjects.map((subject, idx) => (
                        <Badge key={idx} variant="outline">
                          {subject}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {overview.sample_topics.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium mb-2">Sample Topics:</h3>
                    <div className="space-y-2">
                      {overview.sample_topics.map((topic, idx) => (
                        <div key={idx} className="bg-muted rounded p-3">
                          <div className="font-medium text-sm">{topic.subject}</div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {topic.content_preview}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
