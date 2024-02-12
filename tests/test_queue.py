
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
MOCK_GUILD._state = Fake()



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

    def test_shifting(self):
        self.append_tracks()

        item0 = self.queue[0]
        self.queue.shift_track(1)

        self.assertEqual(self.queue[-1],item0)

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
