import { createServer } from 'vite'

const server = await createServer({
  server: {
    host: '0.0.0.0',
    port: 5173
  }
})

await server.listen()
console.log('Server running at http://localhost:5173/')