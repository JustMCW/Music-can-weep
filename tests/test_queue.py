
import unittest
import discord
from music import SongQueue,SongTrack
from unittest.mock import patch
from custom_errors import QueueEmpty


class Fake:
    def _get_voice_client(*_):
        return None

MOCK_GUILD = discord.Guild.__new__(discord.Guild)
MOCK_GUILD.name = "Test"
MOCK_GUILD.id = 69



class Test_Queue(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = SongQueue(MOCK_GUILD)

    def append_tracks(self, count=5):
        for i in range(count):
            self.queue.append(
                SongTrack(
                    title=str(i),
                    duration=i,
                    thumbnail="",
                    webpage_url="",
                    source_url="",
                ))

    def test_boolean(self):
        self.assertEqual(bool(self.queue),False)
        self.assertEqual(len(self.queue),0)

        self.append_tracks()

        self.assertEqual(bool(self.queue),True)
        self.assertGreater(len(self.queue),0)

    def test_shift(self):
        self.append_tracks()

        item0 = self.queue[0]
        self.queue.shift_track(1)

        self.assertEqual(self.queue[-1],item0)

    def test_skip(self):
        self.append_tracks(5)
        item0 = self.queue[0]
        
        self.queue.skip()
        self.assertEqual(len(self.queue),4)
        self.assertEqual(self.queue.history[0],item0)
        
        with self.assertRaises(ValueError):
            self.queue.skip(69)
    
    def test_next(self):  
        self.append_tracks(5)
        item0 = self.queue[0]
        
        self.queue.next()
        self.assertEqual(len(self.queue),4)
        self.assertEqual(self.queue.history[0],item0)
        
        with self.assertRaises(ValueError):
            self.queue.next(69)
         
        self.queue.queue_looping = True
        self.queue.next(2)
        self.assertEqual(len(self.queue), 4)

    def test_retrieve(self):
        self.assertEqual(self.queue.queue_looping, False)
        
        with self.assertRaises(ValueError):
            self.queue.retrieve()
        
        self.append_tracks(5)
        
        item0 = self.queue.poplefttohistory()
        self.assertEqual(self.queue.history[0], item0)

        self.queue.retrieve()
        self.assertEqual(self.queue[0], item0)
        
        self.queue.skip(3)
        self.assertEqual(len(self.queue.history), 3)
        
        self.queue.retrieve(2)
        self.assertEqual(len(self.queue.history),1)
        self.assertEqual(self.queue.history[0],item0)

        with self.assertRaises(ValueError):
            self.queue.retrieve(69)
            
        self.queue.retrieve(1)
        self.assertEqual(len(self.queue),5)

    def test_swap(self):
        self.assertRaises(QueueEmpty,self.queue.swap,1,1)

        self.append_tracks()

        self.assertRaises(IndexError,self.queue.swap,len(self.queue)+1,0)
        self.assertRaises(IndexError,self.queue.swap,0,len(self.queue)+1)

        item0 = self.queue[0]
        item1 = self.queue[1]
        self.queue.swap(0,1)
        self.assertEqual(self.queue[0],item1)
        self.assertEqual(self.queue[1],item0)


if __name__ == "__main__":

    unittest.main()
