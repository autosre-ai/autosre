"use client";

import { useState } from "react";
import { Search, Brain, Clock, CheckCircle, AlertTriangle, Trash2 } from "lucide-react";
import { useEpisodes, useMemory, useSearchEpisodes } from "@/lib/hooks";
import { EpisodeCard } from "@/components/EpisodeCard";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { formatDuration } from "@/lib/utils";

export default function MemoryPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"episodes" | "strategies">("episodes");
  
  const { data: episodes, isLoading: loadingEpisodes } = useEpisodes();
  const { data: memory, isLoading: loadingMemory } = useMemory();
  const { search, results: searchResults, isSearching, clearResults } = useSearchEpisodes();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      search(searchQuery);
    } else {
      clearResults();
    }
  };

  const displayedEpisodes = searchResults || episodes || [];
  const stats = memory?.stats;
  const strategies = memory?.strategies || [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Brain className="w-8 h-8" />
          Memory Browser
        </h1>
        <p className="text-muted-foreground mt-1">
          Browse past investigations, search for similar incidents, and review learned strategies
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-purple-500/10">
                <Brain className="w-6 h-6 text-purple-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats?.totalEpisodes || 0}</p>
                <p className="text-sm text-muted-foreground">Episodes</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-green-500/10">
                <CheckCircle className="w-6 h-6 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats?.resolvedCount || 0}</p>
                <p className="text-sm text-muted-foreground">Resolved</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-orange-500/10">
                <Clock className="w-6 h-6 text-orange-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {stats?.averageDuration
                    ? formatDuration(stats.averageDuration)
                    : "N/A"}
                </p>
                <p className="text-sm text-muted-foreground">Avg Duration</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-blue-500/10">
                <AlertTriangle className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{strategies.length}</p>
                <p className="text-sm text-muted-foreground">Strategies</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search for similar incidents..."
                className="w-full pl-10 pr-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <Button type="submit" disabled={isSearching}>
              {isSearching ? "Searching..." : "Search"}
            </Button>
            {searchResults && (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  clearResults();
                  setSearchQuery("");
                }}
              >
                Clear
              </Button>
            )}
          </form>
          {searchResults && (
            <p className="text-sm text-muted-foreground mt-2">
              Found {searchResults.length} similar episode(s)
            </p>
          )}
        </CardContent>
      </Card>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveTab("episodes")}
          className={`px-4 py-2 border-b-2 transition-colors ${
            activeTab === "episodes"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Episodes
        </button>
        <button
          onClick={() => setActiveTab("strategies")}
          className={`px-4 py-2 border-b-2 transition-colors ${
            activeTab === "strategies"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Strategies
        </button>
      </div>

      {/* Content */}
      {activeTab === "episodes" ? (
        <div className="space-y-4">
          {loadingEpisodes ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-32 bg-muted animate-pulse rounded-lg" />
              ))}
            </div>
          ) : displayedEpisodes.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                <p className="text-lg font-medium">No episodes yet</p>
                <p className="text-sm text-muted-foreground">
                  Complete investigations will be stored here for future reference
                </p>
              </CardContent>
            </Card>
          ) : (
            displayedEpisodes.map((episode) => (
              <EpisodeCard key={episode.id} episode={episode} />
            ))
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loadingMemory ? (
            [...Array(4)].map((_, i) => (
              <div key={i} className="h-48 bg-muted animate-pulse rounded-lg" />
            ))
          ) : strategies.length === 0 ? (
            <Card className="md:col-span-2">
              <CardContent className="py-12 text-center">
                <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                <p className="text-lg font-medium">No strategies learned yet</p>
                <p className="text-sm text-muted-foreground">
                  Strategies are extracted from successful investigations
                </p>
              </CardContent>
            </Card>
          ) : (
            strategies.map((strategy) => (
              <Card key={strategy.id}>
                <CardHeader>
                  <CardTitle className="text-lg">{strategy.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-4">
                    {strategy.description}
                  </p>
                  <div className="space-y-2 mb-4">
                    <p className="text-xs font-medium text-muted-foreground">Steps:</p>
                    <ol className="list-decimal list-inside text-sm space-y-1">
                      {strategy.steps.slice(0, 5).map((step, idx) => (
                        <li key={idx} className="truncate">
                          {step}
                        </li>
                      ))}
                      {strategy.steps.length > 5 && (
                        <li className="text-muted-foreground">
                          +{strategy.steps.length - 5} more steps
                        </li>
                      )}
                    </ol>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      Used {strategy.usageCount}x
                    </span>
                    <span className="text-green-500">
                      {Math.round(strategy.successRate * 100)}% success
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
