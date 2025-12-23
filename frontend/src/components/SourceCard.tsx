import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Source {
  content: string;
  metadata: Record<string, any>;
  source_class?: number | null;
  rank: number;
}

interface SourceCardProps {
  source: Source;
}

export function SourceCard({ source }: SourceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base">
              Source #{source.rank}
            </CardTitle>
            <div className="flex flex-wrap gap-2">
              {source.source_class && (
                <Badge variant="outline">
                  Class {source.source_class}
                </Badge>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="space-y-3">
          <div>
            <h4 className="text-sm font-medium mb-1">Content:</h4>
            <p className="text-sm text-muted-foreground bg-code rounded p-3 font-mono text-code-foreground">
              {source.content}
            </p>
          </div>

          {Object.keys(source.metadata).length > 0 && (
            <div>
              <h4 className="text-sm font-medium mb-1">Metadata:</h4>
              <div className="bg-code rounded p-3 space-y-1">
                {Object.entries(source.metadata).map(([key, value]) => (
                  <div key={key} className="text-xs font-mono text-code-foreground">
                    <span className="font-semibold">{key}:</span>{" "}
                    {JSON.stringify(value)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
