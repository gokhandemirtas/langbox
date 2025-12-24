#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { MongoClient } from 'mongodb';

// MongoDB connection configuration
const MONGODB_HOST = process.env.MONGODB_HOST || 'localhost';
const MONGODB_PORT = process.env.MONGODB_PORT || '27017';
const MONGODB_USER = process.env.MONGODB_USER || 'admin';
const MONGODB_PASSWORD = process.env.MONGODB_PASSWORD || 'admin';
const MONGODB_DB = process.env.MONGODB_DB || 'langbox';

const mongoUri = `mongodb://${MONGODB_USER}:${MONGODB_PASSWORD}@${MONGODB_HOST}:${MONGODB_PORT}`;

// Initialize MCP server
const server = new Server(
  {
    name: 'langbox-mongodb',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

let mongoClient = null;
let db = null;

// Connect to MongoDB
async function connectMongo() {
  if (!mongoClient) {
    mongoClient = new MongoClient(mongoUri);
    await mongoClient.connect();
    db = mongoClient.db(MONGODB_DB);
    console.error(`Connected to MongoDB: ${MONGODB_DB}`);
  }
  return db;
}

// List available tools
server.setRequestHandler({
  method: 'tools/list'
}, async () => {
  return {
    tools: [
      {
        name: 'list_collections',
        description: 'List all collections in the langbox database',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'query_collection',
        description: 'Query documents from a collection with optional filter and limit',
        inputSchema: {
          type: 'object',
          properties: {
            collection: {
              type: 'string',
              description: 'Collection name (e.g., "conversations", "weather", "credentials", "hueconfiguration")',
            },
            filter: {
              type: 'object',
              description: 'MongoDB query filter (optional, defaults to {})',
            },
            limit: {
              type: 'number',
              description: 'Maximum number of documents to return (optional, defaults to 10)',
            },
          },
          required: ['collection'],
        },
      },
      {
        name: 'count_documents',
        description: 'Count documents in a collection matching a filter',
        inputSchema: {
          type: 'object',
          properties: {
            collection: {
              type: 'string',
              description: 'Collection name',
            },
            filter: {
              type: 'object',
              description: 'MongoDB query filter (optional, defaults to {})',
            },
          },
          required: ['collection'],
        },
      },
      {
        name: 'get_recent_conversations',
        description: 'Get recent conversations from the database',
        inputSchema: {
          type: 'object',
          properties: {
            limit: {
              type: 'number',
              description: 'Number of recent conversations to retrieve (defaults to 5)',
            },
          },
        },
      },
      {
        name: 'search_conversations',
        description: 'Search conversations by question or answer content',
        inputSchema: {
          type: 'object',
          properties: {
            search_text: {
              type: 'string',
              description: 'Text to search for in questions or answers',
            },
            limit: {
              type: 'number',
              description: 'Maximum results (defaults to 10)',
            },
          },
          required: ['search_text'],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler({
  method: 'tools/call'
}, async (request) => {
  const db = await connectMongo();
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'list_collections': {
        const collections = await db.listCollections().toArray();
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                collections.map((c) => c.name),
                null,
                2
              ),
            },
          ],
        };
      }

      case 'query_collection': {
        const { collection, filter = {}, limit = 10 } = args;
        const docs = await db.collection(collection).find(filter).limit(limit).toArray();
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(docs, null, 2),
            },
          ],
        };
      }

      case 'count_documents': {
        const { collection, filter = {} } = args;
        const count = await db.collection(collection).countDocuments(filter);
        return {
          content: [
            {
              type: 'text',
              text: `Count: ${count}`,
            },
          ],
        };
      }

      case 'get_recent_conversations': {
        const { limit = 5 } = args;
        const conversations = await db
          .collection('conversations')
          .find({})
          .sort({ datestamp: -1 })
          .limit(limit)
          .toArray();
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(conversations, null, 2),
            },
          ],
        };
      }

      case 'search_conversations': {
        const { search_text, limit = 10 } = args;
        const conversations = await db
          .collection('conversations')
          .find({
            $or: [
              { question: { $regex: search_text, $options: 'i' } },
              { answer: { $regex: search_text, $options: 'i' } },
            ],
          })
          .limit(limit)
          .toArray();
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(conversations, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('Langbox MongoDB MCP server running');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
